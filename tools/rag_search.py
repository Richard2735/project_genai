"""
tools/rag_search.py — Tool 2: Busqueda RAG (Retrieval Augmented Generation)

Esta herramienta busca informacion relevante en la base de conocimiento
corporativa usando busqueda semantica REAL con FAISS + Gemini Embeddings.

¿Como funciona la busqueda semantica?
--------------------------------------
1. El usuario hace una pregunta: "¿Cual es la politica de teletrabajo?"
2. La pregunta se convierte en un vector de 768 numeros (embedding)
3. FAISS compara ese vector contra TODOS los vectores de la base
4. Retorna los K fragmentos cuyos vectores son mas "cercanos"
   (cercano = significado similar, no palabras exactas)
5. El agente usa esos fragmentos como contexto para generar su respuesta

Ventaja sobre keywords:
  - "trabajo remoto" encuentra resultados sobre "teletrabajo"
  - "proteccion de datos personales" encuentra resultados sobre "GDPR"
  - Funciona con sinonimos, parafraseos y diferentes idiomas

Modos de operacion:
  - Con indice FAISS (vectorstore/): Busqueda semantica real
  - Sin indice (fallback): Busqueda por keywords sobre datos mock
"""

import re
from pathlib import Path
from langchain_classic.tools import tool

from config.settings import (
    GOOGLE_API_KEY,
    GCP_PROJECT_ID,
    GCP_REGION,
    USE_VERTEX_AI,
    EMBEDDING_MODEL,
    FAISS_INDEX_DIR,
    RAG_TOP_K,
)

# ========================================
# Base de conocimiento mock (fallback)
# Se usa solo cuando NO hay indice FAISS disponible
# ========================================
MOCK_KNOWLEDGE_BASE = [
    {
        "texto": (
            "Los datos de clientes deben ser anonimizados mediante Cloud DLP "
            "antes de su procesamiento o almacenamiento en sistemas de analisis. "
            "El responsable de cumplimiento debe aprobar cualquier excepcion."
        ),
        "fuente": "Politica_Datos.pdf",
        "pagina": 2,
        "keywords": ["datos", "clientes", "anonimizar", "dlp", "politica", "almacenamiento", "procesamiento"],
    },
    {
        "texto": (
            "El acceso a informacion confidencial requiere autorizacion previa del area de Compliance. "
            "Toda consulta debe ser registrada en el audit log con usuario, fecha y motivo de acceso."
        ),
        "fuente": "Politica_Confidencialidad.pdf",
        "pagina": 1,
        "keywords": ["acceso", "confidencial", "autorizacion", "compliance", "audit", "log", "politica"],
    },
    {
        "texto": (
            "La politica de seguridad de la informacion establece que las contrasenas deben tener "
            "minimo 12 caracteres, combinando mayusculas, minusculas, numeros y simbolos. "
            "Se requiere rotacion cada 90 dias."
        ),
        "fuente": "Politica_Seguridad_IT.pdf",
        "pagina": 4,
        "keywords": ["seguridad", "contrasena", "password", "politica", "it", "informacion"],
    },
    {
        "texto": (
            "La politica de teletrabajo establece que los colaboradores deben usar VPN corporativa "
            "para acceder a sistemas internos, mantener el equipo con antivirus actualizado "
            "y nunca trabajar desde redes WiFi publicas sin VPN activa."
        ),
        "fuente": "Politica_Teletrabajo.pdf",
        "pagina": 2,
        "keywords": ["teletrabajo", "remoto", "vpn", "wifi", "seguridad", "politica", "colaborador"],
    },
]

# ========================================
# Cache del vector store FAISS
# Se carga una sola vez y se reutiliza en cada consulta
# ========================================
_vectorstore_cache = None
_usando_faiss = False


def _cargar_vectorstore():
    """
    Carga el indice FAISS desde disco.

    ¿Que sucede aqui?
    1. Verifica si existe el directorio vectorstore/ con el indice
    2. Si existe: carga el indice FAISS + el modelo de embeddings
       - FAISS necesita el modelo de embeddings para convertir
         las nuevas queries en vectores del mismo espacio
    3. Si no existe: retorna None (se usara fallback mock)

    El resultado se cachea en _vectorstore_cache para no recargar
    el indice en cada consulta (el indice puede pesar varios MB).
    """
    global _vectorstore_cache, _usando_faiss

    if _vectorstore_cache is not None:
        return _vectorstore_cache

    # Verificar si existe el indice FAISS en disco
    faiss_file = FAISS_INDEX_DIR / "index.faiss"
    if not faiss_file.exists():
        print("[RAG] No se encontro indice FAISS en vectorstore/")
        print("[RAG] Usando fallback: busqueda por keywords (mock)")
        print("[RAG] Para crear el indice ejecuta: python scripts/ingestar_documentos.py")
        _usando_faiss = False
        return None

    # Cargar FAISS desde disco
    try:
        from langchain_community.vectorstores import FAISS

        print(f"[RAG] Cargando indice FAISS desde {FAISS_INDEX_DIR}/...")

        # Necesitamos el mismo modelo de embeddings que se uso para crear el indice
        # para que las queries se conviertan al mismo espacio vectorial
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

        _vectorstore_cache = FAISS.load_local(
            str(FAISS_INDEX_DIR),
            embeddings,
            allow_dangerous_deserialization=True  # Necesario para cargar .pkl
        )

        num_docs = _vectorstore_cache.index.ntotal
        print(f"[RAG] Indice FAISS cargado: {num_docs} vectores")
        _usando_faiss = True
        return _vectorstore_cache

    except Exception as e:
        print(f"[RAG] Error cargando FAISS: {e}")
        print("[RAG] Usando fallback: busqueda por keywords (mock)")
        _usando_faiss = False
        return None


def recargar_vectorstore():
    """
    Fuerza la recarga del indice FAISS.
    Util despues de ejecutar una nueva ingesta.
    """
    global _vectorstore_cache, _usando_faiss
    _vectorstore_cache = None
    _usando_faiss = False
    return _cargar_vectorstore()


def _busqueda_faiss(query: str, top_k: int = RAG_TOP_K) -> str:
    """
    Busqueda semantica real usando FAISS.

    ¿Que hace internamente?
    1. Recibe la query en texto ("politica de teletrabajo")
    2. El modelo de embeddings la convierte en un vector de 768 dims
    3. FAISS calcula la distancia entre ese vector y TODOS los del indice
    4. Retorna los top_k mas cercanos (menor distancia = mas similar)
    5. Formatea los resultados con metadata (fuente, pagina, categoria)

    El score es la distancia L2 (euclidiana). Menor = mas relevante.
    Tipicamente: < 0.5 = muy relevante, 0.5-1.0 = relevante, > 1.0 = poco relevante

    Args:
        query: Pregunta del usuario
        top_k: Numero de resultados a retornar

    Returns:
        Texto formateado con los resultados
    """
    vectorstore = _cargar_vectorstore()

    # similarity_search_with_score retorna [(Document, score), ...]
    # score = distancia L2 (menor = mas similar)
    resultados = vectorstore.similarity_search_with_score(query, k=top_k)

    if not resultados:
        return (
            f"Resultados de busqueda para: '{query}'\n\n"
            f"No se encontraron fragmentos relevantes.\n"
            f"Contacta al equipo de Data Governance para consultas especificas."
        )

    # Formatear resultados
    lineas = [f"Resultados de busqueda para: '{query}'\n"]
    lineas.append(f"[Busqueda semantica FAISS — {_vectorstore_cache.index.ntotal} fragmentos indexados]\n")

    for i, (doc, score) in enumerate(resultados, 1):
        # Convertir distancia L2 a relevancia (1/(1+dist)) para mostrar intuitivamente
        relevancia = 1 / (1 + score)
        relevancia_pct = relevancia * 100

        categoria = doc.metadata.get("categoria", "N/A")
        fuente = doc.metadata.get("fuente", "Desconocido")
        pagina = doc.metadata.get("pagina", "?")

        lineas.append(
            f"[Resultado {i} — Relevancia: {relevancia_pct:.1f}%]\n"
            f"Doc: {fuente}, pag. {pagina} | Categoria: {categoria}\n"
            f"{doc.page_content}"
        )

    return "\n\n".join(lineas)


def _busqueda_mock(query: str, top_k: int = RAG_TOP_K) -> str:
    """
    Busqueda por keywords sobre datos mock (fallback).
    Se usa cuando no hay indice FAISS disponible.
    """
    query_tokens = re.findall(r'\b\w+\b', query.lower())

    scored = []
    for fragmento in MOCK_KNOWLEDGE_BASE:
        keywords_lower = [kw.lower() for kw in fragmento["keywords"]]
        coincidencias = sum(1 for token in set(query_tokens) if token in keywords_lower)
        scored.append((fragmento, coincidencias))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_resultados = scored[:top_k]

    if top_resultados[0][1] == 0:
        return (
            f"Resultados de busqueda para: '{query}'\n\n"
            f"No se encontraron fragmentos con alta relevancia para esta consulta.\n"
            f"Contacta al equipo de Data Governance para consultas especificas."
        )

    lineas = [f"Resultados de busqueda para: '{query}'\n"]
    lineas.append("[Busqueda por keywords — modo fallback (sin indice FAISS)]\n")

    for i, (fragmento, score) in enumerate(top_resultados, 1):
        if score == 0:
            break
        lineas.append(
            f"[Resultado {i} — Relevancia: {score} pts]\n"
            f"Doc: {fragmento['fuente']}, pag. {fragmento['pagina']}\n"
            f"{fragmento['texto']}"
        )

    return "\n\n".join(lineas)


@tool
def rag_search_tool(query: str) -> str:
    """
    Busca informacion relevante en los documentos internos de la empresa
    usando busqueda semantica con FAISS y embeddings de Gemini.

    Esta herramienta implementa el patron RAG (Retrieval Augmented Generation):
    1. Convierte la pregunta en un embedding vectorial (768 dimensiones)
    2. Busca los fragmentos mas similares en el indice FAISS
    3. Devuelve los top-k resultados con referencia al documento fuente

    La base de conocimiento incluye PDFs corporativos cargados desde Google Drive:
    - Politicas (seguridad, teletrabajo, datos, anticorrupcion, etc.)
    - Procedimientos (calidad, incidentes, onboarding, etc.)
    - Reglamentos (reglamento interno de trabajo, etc.)

    Usala cuando el usuario haga preguntas sobre:
    - Politicas corporativas (datos, seguridad, confidencialidad, teletrabajo)
    - Manuales tecnicos y de operaciones
    - Procedimientos de calidad, onboarding, incidentes
    - Regulaciones y compliance
    - Reglamentos internos de la empresa

    Args:
        query (str): Pregunta o tema a buscar en los documentos corporativos

    Returns:
        str: Top-3 fragmentos mas relevantes con referencia al documento fuente,
             numero de pagina y score de relevancia
    """
    # Intentar busqueda semantica con FAISS
    vectorstore = _cargar_vectorstore()

    if vectorstore is not None:
        return _busqueda_faiss(query)
    else:
        return _busqueda_mock(query)
