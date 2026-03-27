"""
config/settings.py — Configuración centralizada del proyecto

Centraliza todas las variables de entorno y rutas del proyecto.
Valida que las credenciales existan antes de ejecutar el agente.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ================================
# Rutas del proyecto
# ================================
PROJECT_ROOT = Path(__file__).parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
DOCS_DIR = PROJECT_ROOT / "docs" / "corporativos"
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
SERVICE_ACCOUNT_FILE = CREDENTIALS_DIR / "service_account.json"

# ================================
# Google API
# ================================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# ================================
# Google Drive
# ================================
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")

# ================================
# Google Cloud Platform
# ================================
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")

# Flag para usar Vertex AI (con créditos GCP) en lugar de Google AI Studio (API key gratis)
# True = Vertex AI (text-embedding-004, ChatVertexAI)
# False = Google AI Studio (embedding-001, ChatGoogleGenerativeAI)
USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "true").lower() == "true"

# ================================
# Configuración del agente
# ================================
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
MEMORY_WINDOW_K = int(os.getenv("MEMORY_WINDOW_K", "5"))
AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "5"))

# ================================
# RAG - Configuración de fragmentación
# ================================
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# ================================
# RAG - Embeddings y Vector Store
# ================================
# Modelo de embeddings:
#   Vertex AI:          text-embedding-004 (768 dims, mejor calidad)
#   Google AI Studio:   models/embedding-001 (768 dims, gratis)
_DEFAULT_EMBEDDING = "text-embedding-004" if USE_VERTEX_AI else "models/embedding-001"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", _DEFAULT_EMBEDDING)
# Directorio donde se persiste el índice FAISS a disco
FAISS_INDEX_DIR = PROJECT_ROOT / "vectorstore"

# ================================
# Drive API Scopes
# ================================
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def validar_configuracion() -> dict:
    """
    Valida que las configuraciones necesarias estén presentes.
    Retorna un dict con el estado de cada componente.
    """
    estado = {
        "google_api_key": bool(GOOGLE_API_KEY),
        "drive_folder_id": bool(DRIVE_FOLDER_ID),
        "service_account": SERVICE_ACCOUNT_FILE.exists(),
        "docs_dir": DOCS_DIR.exists(),
        "faiss_index": FAISS_INDEX_DIR.exists() and any(FAISS_INDEX_DIR.glob("*.faiss")),
    }
    return estado


def imprimir_estado():
    """Imprime el estado de configuración en consola."""
    estado = validar_configuracion()
    print("\n📋 Estado de configuración:")
    for componente, ok in estado.items():
        icono = "✅" if ok else "❌"
        print(f"  {icono} {componente}")
    print()
    return estado
