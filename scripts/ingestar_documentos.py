"""
scripts/ingestar_documentos.py — Pipeline de ingesta de documentos para RAG

Este script implementa el pipeline completo de ingesta:

  1. Lee los PDFs descargados desde docs/corporativos/
  2. Extrae el texto de cada página
  3. Divide el texto en fragmentos (chunks) con solapamiento
  4. Asigna metadata a cada fragmento (categoría, archivo fuente, página)
  5. Genera embeddings vectoriales usando Gemini (text-embedding-004)
  6. Almacena todo en un índice FAISS persistido en disco (vectorstore/)

¿Por qué cada paso?
-------------------
- Fragmentar con overlap: Un PDF de 30 páginas no cabe en el contexto del LLM.
  Lo dividimos en pedazos de ~500 caracteres. El overlap de 100 chars asegura
  que si una idea cruza el límite entre dos fragmentos, no se pierda.

- Metadata: Cada fragmento guarda de dónde vino (archivo, página, categoría).
  Esto permite filtrar búsquedas ("buscar solo en POLITICAS") y citar fuentes.

- Embeddings: Convertimos texto a vectores numéricos de 768 dimensiones.
  Dos textos con significado similar tendrán vectores cercanos en el espacio.
  Esto es lo que permite la "búsqueda semántica" — buscar por significado,
  no por palabras exactas.

- FAISS: Es la "base de datos de vectores". Recibe un vector de consulta
  y encuentra los K vectores más cercanos (similitud coseno). Es de Facebook AI,
  corre 100% local, y se serializa a disco para persistencia.

Uso:
  cd s13/
  python scripts/ingestar_documentos.py

Prerequisitos:
  - PDFs descargados en docs/corporativos/ (ejecutar scripts/descargar_pdfs.py primero)
  - GOOGLE_API_KEY en .env (para generar embeddings con Gemini)
"""

import gc
import sys
import time
from pathlib import Path

# Agregar directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from config.settings import (
    GOOGLE_API_KEY,
    GCP_PROJECT_ID,
    GCP_REGION,
    USE_VERTEX_AI,
    DOCS_DIR,
    FAISS_INDEX_DIR,
    EMBEDDING_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    imprimir_estado,
)
from tools.pdf_processor import procesar_pdf


def crear_documentos_langchain(fragmentos: list[dict]) -> list[Document]:
    """
    Convierte los fragmentos del pdf_processor al formato Document de LangChain.

    Cada Document tiene:
      - page_content: el texto del fragmento
      - metadata: información sobre el origen del fragmento

    ¿Por qué este paso?
    LangChain usa objetos Document como estándar. FAISS necesita este formato
    para poder asociar cada vector con su texto original y metadata.

    Args:
        fragmentos: Lista de dicts del pdf_processor ({texto, fuente, pagina, keywords, categoria})

    Returns:
        Lista de objetos Document de LangChain
    """
    documentos = []
    for frag in fragmentos:
        doc = Document(
            page_content=frag["texto"],
            metadata={
                "fuente": frag["fuente"],           # Nombre del archivo PDF
                "pagina": frag["pagina"],            # Número de página
                "categoria": frag["categoria"],      # POLITICAS, PROCEDIMIENTOS, REGLAMENTOS
                "keywords": ", ".join(frag.get("keywords", [])),  # Keywords como string
            }
        )
        documentos.append(doc)
    return documentos


def generar_indice_faiss(documentos: list[Document]) -> FAISS:
    """
    Genera el índice FAISS a partir de los documentos.

    ¿Qué sucede internamente?
    1. Para cada documento, envía el texto a la API de Gemini
    2. Gemini devuelve un vector de 768 números (el embedding)
    3. FAISS almacena todos los vectores en una estructura optimizada
       para búsqueda rápida por similitud (índice L2/coseno)
    4. También guarda el mapping vector → documento original

    Args:
        documentos: Lista de Documents de LangChain

    Returns:
        Objeto FAISS con el índice construido
    """
    print(f"\n--- Generando embeddings con {EMBEDDING_MODEL} ---")
    print(f"    Esto enviará {len(documentos)} fragmentos a la API de Gemini")
    print(f"    Cada fragmento se convierte en un vector de 768 dimensiones\n")

    # Inicializar el modelo de embeddings
    if USE_VERTEX_AI:
        from langchain_google_vertexai import VertexAIEmbeddings
        print(f"    Usando Vertex AI: {EMBEDDING_MODEL} (proyecto: {GCP_PROJECT_ID})")
        embeddings = VertexAIEmbeddings(
            model_name=EMBEDDING_MODEL,
            project=GCP_PROJECT_ID,
            location=GCP_REGION,
        )
    else:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        print(f"    Usando Google AI Studio: {EMBEDDING_MODEL}")
        embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=GOOGLE_API_KEY,
        )

    # Crear el índice FAISS
    # from_documents() hace todo: genera embeddings + construye el índice
    # Internamente:
    #   1. Toma el page_content de cada Document
    #   2. Lo envía al modelo de embeddings (en lotes para eficiencia)
    #   3. Recibe los vectores
    #   4. Los indexa en FAISS para búsqueda rápida
    inicio = time.time()

    # Procesar en lotes para no saturar la API
    BATCH_SIZE = 20
    vectorstore = None

    for i in range(0, len(documentos), BATCH_SIZE):
        lote = documentos[i:i + BATCH_SIZE]
        lote_num = (i // BATCH_SIZE) + 1
        total_lotes = (len(documentos) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"    Lote {lote_num}/{total_lotes}: procesando {len(lote)} fragmentos...")

        if vectorstore is None:
            # Primer lote: crear el índice
            vectorstore = FAISS.from_documents(lote, embeddings)
        else:
            # Lotes siguientes: agregar al índice existente
            lote_vs = FAISS.from_documents(lote, embeddings)
            vectorstore.merge_from(lote_vs)

        # Pausa breve entre lotes para respetar rate limits de la API
        if i + BATCH_SIZE < len(documentos):
            time.sleep(1)

    duracion = time.time() - inicio
    print(f"\n    Embeddings generados en {duracion:.1f} segundos")

    return vectorstore


def persistir_indice(vectorstore: FAISS, directorio: Path):
    """
    Guarda el índice FAISS en disco.

    ¿Por qué persistir?
    Generar embeddings cuesta tiempo y llamadas a la API. Guardando el índice
    en disco, el agente puede cargarlo instantáneamente al iniciar sin
    necesidad de regenerar los embeddings cada vez.

    Se generan 2 archivos:
      - index.faiss: El índice vectorial (los vectores + estructura de búsqueda)
      - index.pkl: El mapping de vectores a documentos (texto + metadata)

    Args:
        vectorstore: Índice FAISS construido
        directorio: Ruta donde guardar los archivos
    """
    directorio.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(directorio))
    print(f"\n    Indice FAISS guardado en: {directorio}/")
    print(f"    Archivos generados:")
    for archivo in sorted(directorio.iterdir()):
        size_kb = archivo.stat().st_size / 1024
        print(f"      - {archivo.name} ({size_kb:.1f} KB)")


def main():
    print("\n" + "=" * 65)
    print("  Pipeline de Ingesta RAG — Documentos Corporativos")
    print("  (Modo optimizado: bajo consumo de RAM)")
    print("=" * 65)

    # 1. Validar configuración
    estado = imprimir_estado()

    if USE_VERTEX_AI:
        if not GCP_PROJECT_ID:
            print("ERROR: Necesitas GCP_PROJECT_ID en .env para usar Vertex AI")
            sys.exit(1)
        print(f"  Modo: Vertex AI (proyecto: {GCP_PROJECT_ID}, region: {GCP_REGION})")
    else:
        if not estado["google_api_key"]:
            print("ERROR: Necesitas GOOGLE_API_KEY en .env para generar embeddings")
            sys.exit(1)
        print("  Modo: Google AI Studio (API key gratuita)")

    # 2. Inicializar modelo de embeddings (una sola vez)
    print("\n  Inicializando modelo de embeddings...")
    if USE_VERTEX_AI:
        from langchain_google_vertexai import VertexAIEmbeddings
        embeddings = VertexAIEmbeddings(
            model_name=EMBEDDING_MODEL,
            project=GCP_PROJECT_ID,
            location=GCP_REGION,
        )
    else:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=GOOGLE_API_KEY,
        )

    # 3. Buscar PDFs
    pdfs = sorted(DOCS_DIR.rglob("*.pdf"))
    if not pdfs:
        print("ERROR: No hay PDFs en docs/corporativos/")
        sys.exit(1)
    print(f"\n  Encontrados {len(pdfs)} PDFs")

    # 4. Procesar PDF por PDF (bajo consumo de RAM)
    # En vez de cargar todos los fragmentos en memoria y despues generar embeddings,
    # procesamos cada PDF individualmente: fragmentar → embeddings → agregar al indice → liberar
    print("\n" + "=" * 65)
    print("  Procesando PDF por PDF (fragmentar + embeddings + FAISS)")
    print("=" * 65)

    vectorstore = None
    total_fragmentos = 0
    total_pdfs = 0
    categorias = {}
    inicio = time.time()
    CHECKPOINT_CADA = 5  # Guardar a disco cada N PDFs para liberar RAM

    for idx, pdf in enumerate(pdfs, 1):
        try:
            # Fragmentar este PDF
            fragmentos = procesar_pdf(pdf)
            if not fragmentos:
                print(f"  [{idx}/{len(pdfs)}] {pdf.name}: 0 fragmentos (vacio)")
                continue

            # Convertir a Documents de LangChain
            documentos = crear_documentos_langchain(fragmentos)
            del fragmentos  # Liberar fragmentos crudos inmediatamente

            # Contar por categoría
            for doc in documentos:
                cat = doc.metadata["categoria"]
                categorias[cat] = categorias.get(cat, 0) + 1

            # Generar embeddings y agregar al indice FAISS
            # Usamos add_documents (in-place) en vez de from_documents + merge
            # para evitar duplicar memoria con indices temporales
            # Reintentos con backoff exponencial para manejar 429 RESOURCE_EXHAUSTED
            BATCH_SIZE = 5
            MAX_RETRIES = 5
            for i in range(0, len(documentos), BATCH_SIZE):
                lote = documentos[i:i + BATCH_SIZE]
                for intento in range(MAX_RETRIES):
                    try:
                        if vectorstore is None:
                            vectorstore = FAISS.from_documents(lote, embeddings)
                        else:
                            vectorstore.add_documents(lote)
                        break  # Exito, salir del retry
                    except Exception as e:
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            espera = 2 ** (intento + 1)  # 2, 4, 8, 16, 32 segundos
                            print(f"    Rate limit, reintentando en {espera}s... ({intento+1}/{MAX_RETRIES})")
                            time.sleep(espera)
                        else:
                            raise  # Error diferente, propagar
                else:
                    print(f"    WARN: No se pudo procesar lote tras {MAX_RETRIES} intentos")
                time.sleep(2)  # Pausa entre lotes para respetar rate limits

            total_fragmentos += len(documentos)
            total_pdfs += 1
            print(f"  [{idx}/{len(pdfs)}] {pdf.name}: {len(documentos)} fragmentos OK")

            # Liberar memoria
            del documentos
            gc.collect()

            # Checkpoint: guardar a disco cada N PDFs y recargar
            # Esto fuerza a Python a liberar la memoria acumulada
            if total_pdfs % CHECKPOINT_CADA == 0 and vectorstore is not None:
                print(f"  ** Checkpoint: guardando indice parcial ({total_fragmentos} fragmentos)...")
                FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
                vectorstore.save_local(str(FAISS_INDEX_DIR))
                del vectorstore
                gc.collect()
                time.sleep(1)
                # Recargar desde disco (memoria limpia)
                vectorstore = FAISS.load_local(
                    str(FAISS_INDEX_DIR), embeddings,
                    allow_dangerous_deserialization=True
                )
                print(f"  ** Checkpoint OK, continuando...")

        except Exception as e:
            print(f"  [{idx}/{len(pdfs)}] {pdf.name}: ERROR - {e}")

    duracion = time.time() - inicio

    if vectorstore is None:
        print("ERROR: No se pudo generar el indice FAISS")
        sys.exit(1)

    # 5. Persistir índice final en disco
    print("\n" + "=" * 65)
    print("  Guardando indice FAISS en disco")
    print("=" * 65)
    persistir_indice(vectorstore, FAISS_INDEX_DIR)

    # 6. Prueba rápida (recargar desde disco para liberar RAM del vectorstore grande)
    print("\n" + "=" * 65)
    print("  Prueba rapida de busqueda semantica")
    print("=" * 65)
    del vectorstore
    gc.collect()
    vectorstore = FAISS.load_local(
        str(FAISS_INDEX_DIR), embeddings,
        allow_dangerous_deserialization=True
    )
    query_test = "politica de seguridad de la informacion"
    print(f"\n    Query: '{query_test}'")
    resultados = vectorstore.similarity_search_with_score(query_test, k=3)
    for i, (doc, score) in enumerate(resultados, 1):
        print(f"\n    [Resultado {i}] Score: {score:.4f}")
        print(f"    Fuente: {doc.metadata['fuente']}, pag. {doc.metadata['pagina']}")
        print(f"    Categoria: {doc.metadata['categoria']}")
        print(f"    Texto: {doc.page_content[:150]}...")

    # Resumen
    print("\n" + "=" * 65)
    print("  INGESTA COMPLETADA")
    print("=" * 65)
    print(f"    PDFs procesados:     {total_pdfs}")
    print(f"    Fragmentos totales:  {total_fragmentos}")
    print(f"    Categorias:          {dict(categorias)}")
    print(f"    Tiempo total:        {duracion:.1f} segundos")
    print(f"    Indice FAISS:        {FAISS_INDEX_DIR}/")
    print()


if __name__ == "__main__":
    main()
