"""
api.py — API REST con FastAPI para el Agente Inteligente

Expone el agente LangChain como microservicio HTTP, listo para
desplegarse en Google Cloud Run y ser consumido por el frontend.

Endpoints:
  GET  /             → Redirige a /docs (Swagger UI)
  GET  /api/health   → Health check
  POST /api/chat     → Enviar pregunta al agente
  POST /api/ingest   → Re-ingesta de documentos

Uso local:
  uvicorn api:app --reload --port 8000

Uso en Cloud Run:
  El Dockerfile ejecuta: uvicorn api:app --host 0.0.0.0 --port 8080
"""

import os
import uuid
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

# Cargar variables de entorno antes de importar el agente
load_dotenv()

from agent import setup_agent
from langchain_classic.memory import ConversationBufferWindowMemory

# ================================
# Configuración de logging
# ================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================
# Modelos Pydantic (request/response)
# ================================

class ChatRequest(BaseModel):
    """Modelo de request para /api/chat"""
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Pregunta o mensaje para el agente",
        json_schema_extra={"example": "¿Cuál es la política de teletrabajo?"}
    )
    session_id: str | None = Field(
        default=None,
        description="ID de sesión para mantener historial. Si no se envía, se genera uno nuevo.",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )


class ChatResponse(BaseModel):
    """Modelo de response para /api/chat"""
    response: str = Field(description="Respuesta del agente")
    session_id: str = Field(description="ID de sesión para mantener historial")
    timestamp: str = Field(description="Timestamp UTC de la respuesta")


class HealthResponse(BaseModel):
    """Modelo de response para /api/health"""
    status: str = "ok"
    service: str = "agente-ia-backend"
    timestamp: str
    vertex_ai: bool = False
    tools: list[str] = []


class IngestResponse(BaseModel):
    """Modelo de response para /api/ingest"""
    status: str
    message: str
    documentos_procesados: int = 0


# ================================
# Estado global de la aplicación
# ================================

# Almacén de sesiones: {session_id: AgentExecutor}
# Cada sesión tiene su propia instancia de memoria
_sessions: dict[str, object] = {}

# Agente base (se usa como template para crear sesiones)
_base_agent = None

# Configuración
MAX_SESSIONS = 100  # Límite de sesiones en memoria
SESSION_TIMEOUT_HOURS = 2  # Tiempo de vida de una sesión (simplificado)


# ================================
# Inicialización de FastAPI
# ================================

app = FastAPI(
    title="Agente IA - API REST",
    description=(
        "API REST para el Agente Inteligente con LangChain.\n\n"
        "Herramientas disponibles:\n"
        "- **data_prep_tool**: Limpieza y conversión de texto a JSONL\n"
        "- **rag_search_tool**: Búsqueda semántica en documentos corporativos\n"
        "- **dlp_anonymizer_tool**: Anonimización de datos sensibles (PII)\n"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — permite requests desde el frontend
# En producción, reemplazar "*" con el dominio real de Vercel
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================
# Eventos del ciclo de vida
# ================================

@app.on_event("startup")
async def startup_event():
    """
    Se ejecuta al arrancar el servidor.
    Inicializa el agente base que se usará como template para cada sesión.
    """
    global _base_agent
    logger.info("Iniciando Agente IA Backend...")

    try:
        _base_agent = setup_agent()
        tools_names = [t.name for t in _base_agent.tools]
        logger.info(f"Agente inicializado con tools: {tools_names}")
    except Exception as e:
        logger.error(f"Error inicializando agente: {e}")
        raise


def _get_or_create_session(session_id: str | None) -> tuple[str, object]:
    """
    Obtiene o crea una sesión con memoria aislada.

    ¿Por qué sesiones separadas?
    El agente usa ConversationBufferWindowMemory para recordar el historial.
    En HTTP cada request es independiente. Sin sesiones, el agente olvidaría
    todo entre requests. Con session_id, el frontend mantiene continuidad.

    Args:
        session_id: ID de sesión existente, o None para crear nueva

    Returns:
        Tupla (session_id, agent_executor)
    """
    global _sessions

    # Generar nuevo session_id si no se proporcionó
    if not session_id or session_id not in _sessions:
        if not session_id:
            session_id = str(uuid.uuid4())

        # Limpiar sesiones antiguas si hay demasiadas
        if len(_sessions) >= MAX_SESSIONS:
            oldest_key = next(iter(_sessions))
            del _sessions[oldest_key]
            logger.info(f"Sesión eliminada por límite: {oldest_key}")

        # Crear nuevo agente con memoria fresca
        _sessions[session_id] = setup_agent()
        logger.info(f"Nueva sesión creada: {session_id}")

    return session_id, _sessions[session_id]


# ================================
# Endpoints
# ================================

@app.get("/", include_in_schema=False)
async def root():
    """Redirige a la documentación Swagger UI"""
    return RedirectResponse(url="/docs")


@app.get("/api/health", response_model=HealthResponse, tags=["Sistema"])
async def health_check():
    """
    Health check del servicio.

    Cloud Run usa este endpoint para verificar que el contenedor está vivo.
    También útil para monitoreo y debugging.
    """
    use_vertex = os.getenv("USE_VERTEX_AI", "true").lower() == "true"
    tools_names = []
    if _base_agent:
        tools_names = [t.name for t in _base_agent.tools]

    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        vertex_ai=use_vertex,
        tools=tools_names,
    )


@app.post("/api/chat", response_model=ChatResponse, tags=["Agente"])
async def chat(request: ChatRequest):
    """
    Envía un mensaje al agente y recibe su respuesta.

    El agente usa el patrón ReAct para decidir si necesita usar alguna
    herramienta (RAG, DLP, Data Prep) o responder directamente.

    - Si envías `session_id`, se mantiene el historial de conversación.
    - Si no envías `session_id`, se crea una sesión nueva.
    """
    if _base_agent is None:
        raise HTTPException(
            status_code=503,
            detail="El agente no está inicializado. Intenta de nuevo en unos segundos."
        )

    try:
        # Obtener o crear sesión
        session_id, agent_executor = _get_or_create_session(request.session_id)

        # Invocar al agente
        logger.info(f"[{session_id[:8]}] Pregunta: {request.message[:100]}...")
        result = agent_executor.invoke({"input": request.message})
        response_text = result["output"]
        logger.info(f"[{session_id[:8]}] Respuesta: {response_text[:100]}...")

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.error(f"Error en /api/chat: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando la consulta: {str(e)}"
        )


@app.post("/api/ingest", response_model=IngestResponse, tags=["Sistema"])
async def ingest_documents():
    """
    Dispara la re-ingesta de documentos corporativos.

    Ejecuta el pipeline: PDFs → Texto → Fragmentos → Embeddings → FAISS

    NOTA: Este proceso puede tardar varios minutos dependiendo de la
    cantidad de documentos. En producción, usar Cloud Tasks o Pub/Sub.
    """
    try:
        from scripts.ingestar_documentos import main as run_ingesta
        logger.info("Iniciando re-ingesta de documentos...")

        # Ejecutar pipeline de ingesta
        run_ingesta()

        # Recargar el vector store en las sesiones activas
        from tools.rag_search import recargar_vectorstore
        recargar_vectorstore()

        return IngestResponse(
            status="ok",
            message="Ingesta completada. Vector store recargado.",
        )

    except Exception as e:
        logger.error(f"Error en /api/ingest: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error durante la ingesta: {str(e)}"
        )


# ================================
# Punto de entrada (desarrollo local)
# ================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Auto-reload en desarrollo
        log_level="info",
    )
