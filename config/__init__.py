"""
config/__init__.py — Paquete de configuración
"""

from .settings import (
    PROJECT_ROOT,
    DOCS_DIR,
    CREDENTIALS_DIR,
    SERVICE_ACCOUNT_FILE,
    GOOGLE_API_KEY,
    DRIVE_FOLDER_ID,
    DRIVE_SCOPES,
    GCP_PROJECT_ID,
    GCP_REGION,
    LLM_MODEL,
    LLM_TEMPERATURE,
    MEMORY_WINDOW_K,
    AGENT_MAX_ITERATIONS,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    RAG_TOP_K,
    EMBEDDING_MODEL,
    FAISS_INDEX_DIR,
    validar_configuracion,
    imprimir_estado,
)
