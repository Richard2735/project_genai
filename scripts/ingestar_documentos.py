"""
scripts/ingestar_documentos.py — Pipeline de ingesta RAG con Document AI

Pipeline completo de ingesta para Cloud Run Job:

  1. Descarga PDFs desde Google Cloud Storage (GCS)
  2. Extrae texto con Document AI (OCR avanzado, como el POC)
  3. Fragmenta el texto con solapamiento (chunks de ~500 chars)
  4. Genera embeddings con text-embedding-004 (via Google AI Studio, SDK ligero)
  5. Construye indice FAISS y lo sube a GCS

¿Por que Document AI en vez de PyPDF?
--------------------------------------
Document AI usa OCR de Google, maneja PDFs escaneados, tablas y layouts
complejos. Es el mismo enfoque del POC anterior (main.py) que funcionaba
correctamente en produccion.

¿Por que google.generativeai en vez de Vertex AI SDK?
------------------------------------------------------
google-cloud-aiplatform consume ~4-6 GB RAM al importarse, lo que causaba
OOM en Cloud Run Job. google.generativeai pesa ~50 MB y genera los mismos
embeddings con text-embedding-004.

IMPORTANTE: Este script NO importa config.settings ni langchain-google-vertexai
para evitar cargar transitivamente google-cloud-aiplatform.

Variables de entorno requeridas:
  GOOGLE_API_KEY          — API key de Google AI Studio
  GCS_BUCKET_NAME         — Bucket GCS con PDFs y donde se sube FAISS
  DOCAI_PROCESSOR_ID      — ID del procesador Document AI
  GCP_PROJECT_ID          — Proyecto GCP
  GCP_REGION              — Region (default: us-central1)
  DOCAI_LOCATION          — Region de Document AI (default: us)

Uso:
  # Cloud Run Job (produccion)
  python scripts/ingestar_documentos.py

  # Local (desarrollo)
  GOOGLE_API_KEY=xxx GCS_BUCKET_NAME=xxx DOCAI_PROCESSOR_ID=xxx python scripts/ingestar_documentos.py
"""

import gc
import os
import sys
import time
import uuid
import pickle
import tempfile

import numpy as np
import faiss as faiss_lib

# LangChain minimo — solo para serializar FAISS en formato compatible con rag_search.py
# NO importamos langchain-google-vertexai ni google-cloud-aiplatform
from langchain_core.documents import Document
from langchain_community.docstore.in_memory import InMemoryDocstore

# Google Cloud — Document AI (extraccion de texto) + Storage (GCS)
from google.cloud import documentai
from google.cloud import storage
from google.api_core.client_options import ClientOptions

# Vertex AI — Embeddings via SDK nativo (TextEmbeddingModel)
# Importamos solo el modulo necesario, no todo google-cloud-aiplatform
import vertexai
from vertexai.language_models import TextEmbeddingModel

# Intentar cargar .env si existe (desarrollo local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ============================================================
# Configuracion desde variables de entorno
# ============================================================
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "")
GCS_PDFS_PREFIX = os.environ.get("GCS_PDFS_PREFIX", "pdfs/")
GCS_VECTORSTORE_PREFIX = os.environ.get("GCS_VECTORSTORE_PREFIX", "vectorstore/")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
GCP_REGION = os.environ.get("GCP_REGION", "us-central1")
DOCAI_PROCESSOR_ID = os.environ.get("DOCAI_PROCESSOR_ID", "")
DOCAI_LOCATION = os.environ.get("DOCAI_LOCATION", "us")

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "100"))
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIM = 768
BATCH_SIZE = 5  # Fragmentos por llamada a la API de embeddings
PAUSE_BETWEEN_BATCHES = 2  # Segundos entre lotes de embeddings

FAISS_INDEX_DIR = os.environ.get("FAISS_INDEX_DIR", "/tmp/vectorstore")


# ============================================================
# Document AI — Extraccion de texto
# ============================================================

def inicializar_docai():
    """Inicializa el cliente de Document AI y retorna el processor_name."""
    endpoint = f"{DOCAI_LOCATION}-documentai.googleapis.com"
    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=endpoint)
    )
    processor_name = client.processor_path(GCP_PROJECT_ID, DOCAI_LOCATION, DOCAI_PROCESSOR_ID)
    return client, processor_name


def _procesar_documento_docai(client, processor_name, pdf_bytes):
    """
    Envia un PDF (<=30 paginas) a Document AI y extrae texto estructurado.

    Returns:
        str: Texto extraido y limpio
    """
    raw_document = documentai.RawDocument(
        content=pdf_bytes, mime_type="application/pdf"
    )
    request = documentai.ProcessRequest(
        name=processor_name, raw_document=raw_document
    )
    response = client.process_document(request=request)
    document = response.document

    textos = []
    for page in document.pages:
        paragraphs_sorted = sorted(
            page.paragraphs,
            key=lambda p: _get_paragraph_start_index(p)
        )

        for paragraph in paragraphs_sorted:
            if _is_header_footer(paragraph):
                continue

            text = _get_text(document, paragraph.layout.text_anchor).strip()
            if not text or len(text) <= 1:
                continue

            text = text.replace('\n', ' ')
            text = text.replace('•', '')
            textos.append(text)

    return "\n".join(textos)


def extraer_texto_docai(client, processor_name, pdf_bytes):
    """
    Extrae texto de un PDF usando Document AI.

    Si el PDF tiene mas de 15 paginas (limite de Document AI OCR),
    lo divide en partes de 15 paginas y procesa cada parte por separado.

    Args:
        client: Cliente DocumentProcessorServiceClient
        processor_name: Ruta completa del procesador
        pdf_bytes: Contenido binario del PDF

    Returns:
        str: Texto extraido y limpio del PDF
    """
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter

    DOCAI_PAGE_LIMIT = 15

    # Verificar numero de paginas
    reader = PdfReader(BytesIO(pdf_bytes))
    total_pages = len(reader.pages)

    if total_pages <= DOCAI_PAGE_LIMIT:
        # PDF dentro del limite, procesar directamente
        return _procesar_documento_docai(client, processor_name, pdf_bytes)

    # PDF excede el limite: dividir en partes de 30 paginas
    print(f"    PDF grande ({total_pages} pags), dividiendo en partes de {DOCAI_PAGE_LIMIT}...")
    textos_partes = []

    for start in range(0, total_pages, DOCAI_PAGE_LIMIT):
        end = min(start + DOCAI_PAGE_LIMIT, total_pages)
        writer = PdfWriter()
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])

        # Serializar la parte a bytes
        buffer = BytesIO()
        writer.write(buffer)
        parte_bytes = buffer.getvalue()

        print(f"    Procesando paginas {start+1}-{end}...")
        texto_parte = _procesar_documento_docai(client, processor_name, parte_bytes)
        textos_partes.append(texto_parte)

        del writer, buffer, parte_bytes
        gc.collect()

    return "\n".join(textos_partes)


def _get_text(document, text_anchor):
    """Extrae texto de un text_anchor de Document AI."""
    response = ""
    segments = sorted(
        text_anchor.text_segments,
        key=lambda s: int(s.start_index or 0)
    )
    for segment in segments:
        start = int(segment.start_index or 0)
        end = int(segment.end_index)
        response += document.text[start:end]
    return response


def _get_paragraph_start_index(paragraph):
    """Obtiene el indice de inicio de un parrafo."""
    if paragraph.layout.text_anchor.text_segments:
        return int(paragraph.layout.text_anchor.text_segments[0].start_index or 0)
    return 0


def _is_header_footer(paragraph):
    """Detecta si un parrafo es header o footer por su posicion Y."""
    vertices = paragraph.layout.bounding_poly.normalized_vertices
    if not vertices:
        return False
    y_values = [v.y for v in vertices]
    center_y = sum(y_values) / len(y_values)
    return center_y < 0.07 or center_y > 0.93


# ============================================================
# Fragmentacion de texto
# ============================================================

def fragmentar_texto(texto, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Divide texto en fragmentos con solapamiento.

    El overlap asegura que si una idea cruza el limite entre dos fragmentos,
    no se pierda contexto. Es una practica estandar en RAG.

    Args:
        texto: Texto completo a fragmentar
        chunk_size: Tamaño maximo de cada fragmento en caracteres
        overlap: Caracteres de solapamiento entre fragmentos consecutivos

    Returns:
        Lista de strings (fragmentos)
    """
    fragmentos = []
    inicio = 0
    while inicio < len(texto):
        fin = inicio + chunk_size
        fragmento = texto[inicio:fin].strip()
        if fragmento:
            fragmentos.append(fragmento)
        inicio += chunk_size - overlap
    return fragmentos


def clasificar_pdf(nombre):
    """
    Clasifica un PDF en categoria segun su nombre.

    Las categorias son consistentes con la estructura de GCS:
    pdfs/POLITICAS/, pdfs/PROCEDIMIENTOS/, pdfs/REGLAMENTOS/
    """
    nombre_lower = nombre.lower()
    if any(kw in nombre_lower for kw in ["politica", "política", "codigo", "código"]):
        return "POLITICAS"
    elif "procedimiento" in nombre_lower:
        return "PROCEDIMIENTOS"
    elif "reglamento" in nombre_lower:
        return "REGLAMENTOS"
    return "OTROS"


# ============================================================
# Embeddings — Google AI Studio (ligero)
# ============================================================

def generar_embeddings_batch(textos, embedding_model, max_retries=7):
    """
    Genera embeddings con Vertex AI SDK nativo (TextEmbeddingModel).

    Usa el mismo modelo (text-embedding-004) que el backend para
    mantener consistencia en el espacio vectorial.

    Incluye reintentos con backoff exponencial para rate limits (429).
    Cada texto se convierte en un vector de 768 dimensiones.

    Args:
        textos: Lista de strings a vectorizar
        embedding_model: Instancia de TextEmbeddingModel
        max_retries: Intentos maximos ante rate limits

    Returns:
        Lista de vectores (listas de floats) o None si falla
    """
    for intento in range(max_retries):
        try:
            results = embedding_model.get_embeddings(textos)
            return [r.values for r in results]
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                espera = min(2 ** (intento + 1), 60)
                print(f"    Rate limit, reintentando en {espera}s... ({intento+1}/{max_retries})")
                time.sleep(espera)
            else:
                raise
    print(f"    ERROR: No se pudo generar embeddings tras {max_retries} intentos")
    return None


# ============================================================
# FAISS — Construccion manual del indice
# ============================================================

def agregar_a_faiss(vectorstore_data, vectors, documentos):
    """
    Agrega vectores y documentos al indice FAISS.

    Construye el indice manualmente (sin FAISS.from_documents de LangChain)
    para evitar importar el SDK pesado de embeddings. El formato final
    es compatible con FAISS.load_local() que usa rag_search.py.

    Args:
        vectorstore_data: Dict con {index, docstore, index_to_id} o None si es nuevo
        vectors: Lista de vectores numpy
        documentos: Lista de Documents de LangChain

    Returns:
        Dict actualizado con el indice FAISS
    """
    vectors_np = np.array(vectors, dtype=np.float32)

    if vectorstore_data is None:
        # Crear indice nuevo
        dim = len(vectors[0])
        index = faiss_lib.IndexFlatL2(dim)
        index.add(vectors_np)
        docstore = InMemoryDocstore()
        index_to_id = {}
        for j, doc in enumerate(documentos):
            doc_id = str(uuid.uuid4())
            docstore.add({doc_id: doc})
            index_to_id[j] = doc_id
        return {"index": index, "docstore": docstore, "index_to_id": index_to_id}
    else:
        # Agregar a indice existente
        start_idx = vectorstore_data["index"].ntotal
        vectorstore_data["index"].add(vectors_np)
        for j, doc in enumerate(documentos):
            doc_id = str(uuid.uuid4())
            vectorstore_data["docstore"].add({doc_id: doc})
            vectorstore_data["index_to_id"][start_idx + j] = doc_id
        return vectorstore_data


def guardar_faiss(vectorstore_data, directorio):
    """
    Guarda el indice FAISS en disco en formato compatible con LangChain.

    Genera 2 archivos:
    - index.faiss: El indice vectorial (vectores + estructura de busqueda)
    - index.pkl: El docstore + mapping (texto + metadata)

    Args:
        vectorstore_data: Dict con {index, docstore, index_to_id}
        directorio: Ruta del directorio de salida
    """
    os.makedirs(directorio, exist_ok=True)
    faiss_lib.write_index(
        vectorstore_data["index"],
        os.path.join(directorio, "index.faiss")
    )
    pkl_data = (vectorstore_data["docstore"], vectorstore_data["index_to_id"])
    with open(os.path.join(directorio, "index.pkl"), "wb") as f:
        pickle.dump(pkl_data, f)


def cargar_faiss(directorio):
    """
    Carga un indice FAISS desde disco.

    Returns:
        Dict con {index, docstore, index_to_id} o None si no existe
    """
    faiss_path = os.path.join(directorio, "index.faiss")
    pkl_path = os.path.join(directorio, "index.pkl")
    if not os.path.exists(faiss_path) or not os.path.exists(pkl_path):
        return None
    index = faiss_lib.read_index(faiss_path)
    with open(pkl_path, "rb") as f:
        docstore, index_to_id = pickle.load(f)
    return {"index": index, "docstore": docstore, "index_to_id": index_to_id}


# ============================================================
# GCS — Subir/descargar vectorstore
# ============================================================

def subir_vectorstore_a_gcs(gcs_client, bucket_name, prefix, directorio):
    """Sube index.faiss e index.pkl a GCS."""
    bucket = gcs_client.bucket(bucket_name)
    for filename in ["index.faiss", "index.pkl"]:
        local_path = os.path.join(directorio, filename)
        if os.path.exists(local_path):
            blob = bucket.blob(f"{prefix}{filename}")
            blob.upload_from_filename(local_path)


def descargar_vectorstore_de_gcs(gcs_client, bucket_name, prefix, directorio):
    """Descarga index.faiss e index.pkl de GCS. Retorna True si existian."""
    os.makedirs(directorio, exist_ok=True)
    bucket = gcs_client.bucket(bucket_name)
    descargados = 0
    for filename in ["index.faiss", "index.pkl"]:
        blob = bucket.blob(f"{prefix}{filename}")
        if blob.exists():
            blob.download_to_filename(os.path.join(directorio, filename))
            descargados += 1
    return descargados == 2


# ============================================================
# Pipeline principal
# ============================================================

def main():
    print("\n" + "=" * 65)
    print("  Pipeline de Ingesta RAG — Document AI + Google AI Studio")
    print("  (Sin google-cloud-aiplatform para evitar OOM)")
    print("=" * 65)

    # --- Validar configuracion ---
    errores = []
    if not GCS_BUCKET_NAME:
        errores.append("GCS_BUCKET_NAME")
    if not DOCAI_PROCESSOR_ID:
        errores.append("DOCAI_PROCESSOR_ID")
    if not GCP_PROJECT_ID:
        errores.append("GCP_PROJECT_ID")
    if errores:
        print(f"  ERROR: Variables de entorno faltantes: {', '.join(errores)}")
        sys.exit(1)

    print(f"  Proyecto:      {GCP_PROJECT_ID}")
    print(f"  Bucket:        gs://{GCS_BUCKET_NAME}")
    print(f"  Document AI:   {DOCAI_LOCATION}/{DOCAI_PROCESSOR_ID}")
    print(f"  Embeddings:    {EMBEDDING_MODEL} (Vertex AI nativo)")
    print(f"  Chunk size:    {CHUNK_SIZE} chars, overlap {CHUNK_OVERLAP}")

    # --- Inicializar clientes ---
    print("\n  Inicializando clientes...")
    vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)
    embedding_model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    gcs_client = storage.Client()
    docai_client, processor_name = inicializar_docai()
    print("  Clientes inicializados OK")

    # --- Listar PDFs en GCS ---
    bucket = gcs_client.bucket(GCS_BUCKET_NAME)
    blobs = list(bucket.list_blobs(prefix=GCS_PDFS_PREFIX))
    pdf_blobs = [b for b in blobs if b.name.lower().endswith(".pdf")]
    print(f"\n  PDFs en GCS: {len(pdf_blobs)}")
    for b in pdf_blobs:
        print(f"    {b.name} ({b.size / 1024:.0f} KB)")

    if not pdf_blobs:
        print("  ERROR: No hay PDFs en el bucket")
        sys.exit(1)

    # --- Intentar reanudar desde checkpoint previo ---
    vectorstore_data = None
    pdfs_ya_procesados = set()

    print(f"\n  Buscando checkpoint en gs://{GCS_BUCKET_NAME}/{GCS_VECTORSTORE_PREFIX}...")
    exito = descargar_vectorstore_de_gcs(gcs_client, GCS_BUCKET_NAME, GCS_VECTORSTORE_PREFIX, FAISS_INDEX_DIR)
    if exito:
        vectorstore_data = cargar_faiss(FAISS_INDEX_DIR)
        if vectorstore_data:
            # Identificar PDFs ya procesados desde metadata
            for doc_id in vectorstore_data["index_to_id"].values():
                doc = vectorstore_data["docstore"].search(doc_id)
                if hasattr(doc, 'metadata') and 'fuente' in doc.metadata:
                    pdfs_ya_procesados.add(doc.metadata['fuente'])
            print(f"  Checkpoint recuperado: {vectorstore_data['index'].ntotal} vectores, "
                  f"{len(pdfs_ya_procesados)} PDFs previos")
    else:
        print("  No hay checkpoint previo, empezando desde cero")

    # --- Procesar PDF por PDF ---
    print("\n" + "=" * 65)
    print("  Procesando PDFs con Document AI")
    print("=" * 65)

    total_fragmentos = 0
    total_pdfs_procesados = 0
    categorias = {}
    inicio_total = time.time()

    for idx, blob in enumerate(pdf_blobs, 1):
        nombre_pdf = os.path.basename(blob.name)

        # Skip si ya fue procesado en un checkpoint anterior
        if nombre_pdf in pdfs_ya_procesados:
            print(f"  [{idx}/{len(pdf_blobs)}] {nombre_pdf}: SKIP (ya procesado)")
            continue

        try:
            # 1. Descargar PDF de GCS
            pdf_bytes = blob.download_as_bytes()

            # 2. Extraer texto con Document AI
            texto = extraer_texto_docai(docai_client, processor_name, pdf_bytes)
            del pdf_bytes
            gc.collect()

            if not texto or len(texto.strip()) < 10:
                print(f"  [{idx}/{len(pdf_blobs)}] {nombre_pdf}: texto vacio, saltando")
                continue

            # 3. Clasificar y fragmentar
            categoria = clasificar_pdf(nombre_pdf)
            fragmentos = fragmentar_texto(texto)
            del texto

            if not fragmentos:
                print(f"  [{idx}/{len(pdf_blobs)}] {nombre_pdf}: 0 fragmentos")
                continue

            # 4. Crear Documents de LangChain con metadata
            documentos = []
            for i, frag in enumerate(fragmentos):
                doc = Document(
                    page_content=frag,
                    metadata={
                        "fuente": nombre_pdf,
                        "pagina": i + 1,  # Document AI no da pagina por fragmento, usamos indice
                        "categoria": categoria,
                        "keywords": "",
                    }
                )
                documentos.append(doc)
            del fragmentos

            # 5. Generar embeddings y agregar a FAISS (lote por lote)
            for i in range(0, len(documentos), BATCH_SIZE):
                lote = documentos[i:i + BATCH_SIZE]
                textos = [d.page_content for d in lote]
                vectors = generar_embeddings_batch(textos, embedding_model)

                if vectors is None:
                    continue

                vectorstore_data = agregar_a_faiss(vectorstore_data, vectors, lote)

                if i + BATCH_SIZE < len(documentos):
                    time.sleep(PAUSE_BETWEEN_BATCHES)

            total_fragmentos += len(documentos)
            total_pdfs_procesados += 1
            categorias[categoria] = categorias.get(categoria, 0) + len(documentos)
            print(f"  [{idx}/{len(pdf_blobs)}] {nombre_pdf}: {len(documentos)} fragmentos — {categoria}")

            del documentos
            gc.collect()

            # 6. Checkpoint despues de cada PDF
            if vectorstore_data is not None:
                print(f"  ** Checkpoint: guardando ({vectorstore_data['index'].ntotal} vectores)...")
                guardar_faiss(vectorstore_data, FAISS_INDEX_DIR)
                subir_vectorstore_a_gcs(gcs_client, GCS_BUCKET_NAME, GCS_VECTORSTORE_PREFIX, FAISS_INDEX_DIR)
                print(f"  ** Checkpoint OK")

        except Exception as e:
            print(f"  [{idx}/{len(pdf_blobs)}] {nombre_pdf}: ERROR - {e}")
            import traceback
            traceback.print_exc()

    duracion = time.time() - inicio_total

    # --- Resultado final ---
    if vectorstore_data is None:
        print("\n  ERROR: No se pudo generar ningun embedding")
        sys.exit(1)

    # Guardar indice final
    print("\n" + "=" * 65)
    print("  Guardando indice FAISS final")
    print("=" * 65)
    guardar_faiss(vectorstore_data, FAISS_INDEX_DIR)
    subir_vectorstore_a_gcs(gcs_client, GCS_BUCKET_NAME, GCS_VECTORSTORE_PREFIX, FAISS_INDEX_DIR)

    faiss_size = os.path.getsize(os.path.join(FAISS_INDEX_DIR, "index.faiss")) / 1024
    pkl_size = os.path.getsize(os.path.join(FAISS_INDEX_DIR, "index.pkl")) / 1024
    print(f"  index.faiss: {faiss_size:.1f} KB")
    print(f"  index.pkl:   {pkl_size:.1f} KB")
    print(f"  GCS:         gs://{GCS_BUCKET_NAME}/{GCS_VECTORSTORE_PREFIX}")

    # --- Resumen ---
    print("\n" + "=" * 65)
    print("  INGESTA COMPLETADA")
    print("=" * 65)
    print(f"  PDFs procesados (esta ejecucion): {total_pdfs_procesados}")
    print(f"  Fragmentos nuevos:                {total_fragmentos}")
    print(f"  Vectores totales en FAISS:        {vectorstore_data['index'].ntotal}")
    print(f"  Categorias:                       {categorias}")
    print(f"  Tiempo:                           {duracion:.0f} segundos")
    print()
    print("  Siguiente paso: el backend de Cloud Run descargara")
    print("  automaticamente este indice de GCS al arrancar.")
    print()


if __name__ == "__main__":
    main()
