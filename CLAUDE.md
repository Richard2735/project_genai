# CLAUDE.md — Proyecto Final IA Generativa

Este archivo proporciona orientación a Claude Code al trabajar con este repositorio. Contiene el contexto completo del proyecto, requisitos técnicos y estado actual.

---

## Objetivo del Proyecto

Desarrollar una **solución de IA generativa completa** que responda preguntas en lenguaje natural usando recuperación aumentada (RAG) y un agente orquestador. La solución debe incluir:

1. **Backend** — API con agente inteligente + pipeline RAG (desplegado en Cloud Run)
2. **Frontend** — Interfaz de consulta web (desplegado en Vercel o Cloud Run)
3. **Despliegue funcional** como microservicio

El agente combina dos iniciativas internas de la consultora:

| Iniciativa | Descripción | Tecnologías |
|---|---|---|
| **3 – Data Prep para LLMs** | Pipeline de limpieza, anonimización y formateo de datos corporativos a JSONL para fine-tuning | Cloud DLP, Cloud Storage |
| **4 – Pipeline RAG** | Motor de búsqueda semántica sobre documentos internos conectado a Gemini | Vector Store, LangChain, Gemini 2.5 Flash, Cloud Run |

---

## Requisitos Técnicos

### Agente y Herramientas

- ✅ Uso de **LangChain** en Python
- ✅ Al menos **1 agente** (ReAct pattern con AgentExecutor)
- ✅ Al menos **2 herramientas propias** (tenemos 3: data_prep, rag_search, dlp_anonymizer)
- ✅ Implementación de **RAG sobre base vectorial** (FAISS con embeddings reales via Vertex AI)
- ✅ **Filtro de búsqueda por metadatos** (categoría, nombre de archivo, página)
- ⬜ (Opcional) Uso de **HyDE** para enriquecer queries antes de la búsqueda vectorial
- ✅ Documentos cargados con **metadata útil** (categoría, fuente, página)

### Backend

- ✅ Agente con herramientas personalizadas
- ✅ Pipeline RAG completo (Document AI → embeddings → FAISS → GCS → retrieval)
- ✅ Ingesta de documentos y vector store persistente (FAISS en GCS)
- ✅ API REST (FastAPI) para exponer el agente como microservicio (`api.py`)
- ✅ Desplegar en **Google Cloud Run**

### Frontend

- ✅ Desarrollado en **Next.js** (TypeScript)
- ✅ Desplegar en **Vercel**
- ✅ Interfaz mínima con:
  - Caja de texto para ingresar preguntas
  - Respuesta del modelo
  - Historial simple de conversación

### README Obligatorio

- ⬜ Descripción del proyecto
- ⬜ Stack tecnológico usado
- ⬜ Estructura del código
- ⬜ Instrucciones paso a paso para ejecutar y desplegar
- ⬜ Cómo probar el agente

---

## Stack Tecnológico

| Capa | Tecnología | Uso |
|------|-----------|-----|
| **LLM (dev)** | Gemini 2.5 Flash (Google AI Studio) | Generación de respuestas + ReAct reasoning. API key gratuita |
| **LLM (prod)** | Gemini via Vertex AI | Mismo modelo pero facturado con créditos GCP (sin rate limit) |
| **Embeddings** | text-embedding-004 (Vertex AI) | Vectorización de documentos para RAG |
| **Framework** | LangChain (`langchain_classic` 1.0.3) | Agente, tools, cadenas RAG, memoria |
| **PDF Extraction** | Document AI (OCR Processor) | Extracción de texto de PDFs con OCR avanzado |
| **Vector Store** | FAISS | Almacenamiento y búsqueda de embeddings |
| **Object Storage** | Cloud Storage (GCS) | PDFs corporativos + índice FAISS persistido |
| **Batch Processing** | Cloud Run Jobs | Ingesta masiva de documentos (2GB RAM, 30min) |
| **Backend API** | FastAPI + Uvicorn | API REST del agente como microservicio |
| **Frontend** | Next.js / React | Interfaz de consulta web |
| **Documentos** | Google Drive API v3 + Service Account | Descarga automática de PDFs corporativos |
| **Anonimización** | Cloud DLP API / regex local | Enmascaramiento de PII |
| **Seguridad** | Secret Manager + `.gitignore` + `.dockerignore` | Gobernanza de datos y credenciales |
| **CI/CD** | Cloud Build + Artifact Registry | Build automático de imágenes Docker |
| **Despliegue backend** | Google Cloud Run | Backend como contenedor Docker |
| **Despliegue frontend** | Vercel | Frontend web |
| **Lenguaje** | Python 3.x (backend), TypeScript (frontend) |
| **Entorno** | `.env` + `python-dotenv` + Secret Manager (prod) | Variables de entorno |

---

## Estructura del proyecto

```
project_genai/
├── agent.py               ← Punto de entrada principal (python agent.py)
├── api.py                 ← ✅ FastAPI server (4 endpoints: chat, health, ingest, docs)
├── test_agent.py          ← Suite de pruebas unitarias
├── requirements.txt       ← Dependencias Python
├── Dockerfile             ← ✅ Contenedor Docker para Cloud Run Service (backend)
├── Dockerfile.job         ← ✅ Contenedor Docker para Cloud Run Job (ingesta)
├── cloudbuild.yaml        ← ✅ Pipeline CI/CD — construye 2 imágenes (backend + ingesta-job)
├── ARQUITECTURA.md        ← ✅ Diagrama de arquitectura completo
├── .env                   ← Variables de entorno (NO subir a git)
├── .env.example           ← Plantilla de variables de entorno
├── .gitignore             ← ✅ Seguridad: excluye .env, credentials, etc.
├── .dockerignore          ← ✅ Seguridad: excluye secretos del contenedor
├── tools/
│   ├── __init__.py
│   ├── data_prep.py       ← Tool 1: limpieza y conversión a JSONL
│   ├── rag_search.py      ← Tool 2: búsqueda semántica vectorial + RAG
│   ├── dlp_anonymizer.py  ← Tool 3: anonimización de PII
│   ├── pdf_processor.py   ← Extracción y fragmentación de PDFs
│   └── drive_loader.py    ← Descarga PDFs desde Google Drive
├── scripts/
│   ├── descargar_pdfs.py  ← Descarga PDFs desde Google Drive
│   └── ingestar_documentos.py ← ✅ Pipeline de ingesta RAG (optimizado para bajo RAM)
├── utils/
│   ├── __init__.py
│   └── gcs_helpers.py     ← Utilidades GCS (descarga PDFs, sube/baja vectorstore)
├── config/
│   └── settings.py        ← Configuración centralizada del proyecto (incluye GCS)
├── credentials/           ← Service Account JSON (gitignored)
├── vectorstore/           ← Índice FAISS persistido (gitignored, se genera con ingesta)
├── docs/
│   ├── corporativos/      ← PDFs descargados y clasificados (POLITICAS/, PROCEDIMIENTOS/, REGLAMENTOS/)
│   └── GCP_SERVICIOS_Y_PERMISOS.md ← Guía completa de configuración GCP
├── frontend/              ← ✅ Next.js app (desplegado en Vercel)
│   ├── package.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── components/
│   │       └── chat.tsx   ← Componente de chat con sesiones y sugerencias
│   └── .env.local         ← NEXT_PUBLIC_API_URL (gitignored)
├── interface/             ← Interfaz local Streamlit (desarrollo)
│   └── app.py
└── .agent/
    ├── commands/test.md
    └── skills/
```

---

## Arquitectura del sistema (Producción)

```
┌─────────────────────┐     HTTPS      ┌──────────────────────────────┐
│   Frontend (Vercel)  │ ──────────────▶│  Cloud Run Service           │
│   Next.js / React    │◀──────────────│  agente-ia-backend           │
│                      │               │                              │
│ • Caja de texto      │               │ • POST /api/chat             │
│ • Respuesta modelo   │               │ • POST /api/ingest           │
│ • Historial chat     │               │ • GET  /api/health           │
└─────────────────────┘               │                              │
                                       │  AgentExecutor (ReAct)       │
                                       │  ├── Gemini 2.5 Flash        │
                                       │  ├── Memoria (k=5)           │
                                       │  └── Tools:                  │
                                       │       ├── data_prep_tool     │
                                       │       ├── rag_search_tool    │
                                       │       └── dlp_anonymizer     │
                                       │                              │
                                       │  Al iniciar:                 │
                                       │  GCS → descarga FAISS index  │
                                       │  → carga en memoria          │
                                       └──────────┬───────────────────┘
                                                  │ lee vectorstore/
                                                  ▼
                                       ┌──────────────────────────────┐
                                       │  Cloud Storage (GCS)         │
                                       │  genai-docs-{PROJECT_ID}     │
                                       │                              │
                                       │  /pdfs/POLITICAS/*.pdf       │
                                       │  /pdfs/PROCEDIMIENTOS/*.pdf  │
                                       │  /pdfs/REGLAMENTOS/*.pdf     │
                                       │  /vectorstore/index.faiss    │
                                       │  /vectorstore/index.pkl      │
                                       └──────────┬───────────────────┘
                                                  ▲ escribe vectorstore/
                                                  │ lee pdfs/
                                       ┌──────────┴───────────────────┐
                                       │  Cloud Run Job               │
                                       │  ingesta-rag-job             │
                                       │  (2 GB RAM, 2 vCPU, 30m)    │
                                       │                              │
                                       │  1. Descarga PDFs de GCS     │
                                       │  2. Fragmenta texto          │
                                       │  3. Genera embeddings        │
                                       │     (Vertex AI text-emb-004) │
                                       │  4. Construye índice FAISS   │
                                       │  5. Sube índice a GCS        │
                                       └──────────────────────────────┘
```

### Principios de la arquitectura

| Principio | Implementación |
|---|---|
| **Stateless containers** | Contenedores no guardan estado; todo persiste en GCS |
| **Separación compute/storage** | PDFs e índice en GCS, procesamiento en Cloud Run |
| **Mínimo privilegio** | SA `cloudrun-agent-sa` con solo los roles necesarios |
| **Inmutabilidad** | Imágenes Docker versionadas en Artifact Registry |
| **Batch vs Serving** | Job para ingesta pesada, Service para consultas en tiempo real |

---

## Pipeline RAG (Retrieval-Augmented Generation)

### Flujo de ingesta

```
GCS (PDFs) → Document AI (OCR) → TextSplitter → Embeddings (Vertex AI) → FAISS → GCS
                                        │
                                        ▼
                                   Metadata por chunk:
                                   • categoria (POLITICAS, PROCEDIMIENTOS, etc.)
                                   • fuente (nombre archivo)
                                   • pagina
```

### Flujo de consulta

```
Query usuario → [HyDE (opcional)] → Embedding query → Vector Search + Metadata Filter → Top-K chunks → LLM → Respuesta
```

### Filtros de metadatos

```python
# Ejemplo: buscar solo en POLITICAS
retriever.search(query, filter={"categoria": "POLITICAS"})

# Ejemplo: buscar en un archivo específico
retriever.search(query, filter={"archivo_fuente": "Politica-Seguridad.pdf"})
```

### HyDE (Hypothetical Document Embeddings) — Opcional

Genera un documento hipotético antes de buscar, mejorando la relevancia:

```
Query → LLM genera respuesta hipotética → Embedding de la hipótesis → Vector Search → Chunks reales → LLM → Respuesta final
```

---

## Las 3 herramientas personalizadas

### Tool 1: `data_prep_tool` (`tools/data_prep.py`)

- **Qué hace**: Recibe texto crudo, elimina ruido (HTML, caracteres especiales) y lo convierte a JSONL para fine-tuning.
- **Cuándo**: Cuando el usuario pide limpiar o preparar texto para entrenamiento.
- **Prod**: Cloud Dataflow (Apache Beam) + BigQuery ML.

### Tool 2: `rag_search_tool` (`tools/rag_search.py`)

- **Qué hace**: Busca fragmentos relevantes en la base de conocimiento usando similitud semántica con filtros de metadatos.
- **Cuándo**: Cuando el usuario pregunta sobre políticas, manuales o documentos internos.
- **Prod**: Vertex AI Vector Search + Vertex AI Embeddings API.

### Tool 3: `dlp_anonymizer_tool` (`tools/dlp_anonymizer.py`)

- **Qué hace**: Detecta y enmascara PII (emails, teléfonos, DNI, RUC, tarjetas).
- **Cuándo**: Antes de procesar texto con datos sensibles.
- **Prod**: Google Cloud DLP API.

---

## Configuración del entorno

### Variables de entorno (`.env`)

```env
# Obligatorio
GOOGLE_API_KEY=tu_clave_aqui

# Google Drive — Service Account
GOOGLE_SERVICE_ACCOUNT_JSON=credentials/service_account.json
DRIVE_FOLDER_ID=id_carpeta_drive

# Despliegue
GCP_PROJECT_ID=tu-proyecto-gcp
GCP_REGION=us-central1
```

### Instalación

```bash
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tu GOOGLE_API_KEY
```

---

## Cómo ejecutar

```bash
# Verificar que todo funciona
python test_agent.py

# Ejecutar el agente en modo conversación (local)
python agent.py

# Ejecutar backend API (FastAPI)
uvicorn api:app --reload --port 8000

# Ejecutar interfaz local (Streamlit)
streamlit run interface/app.py

# Frontend (Next.js)
cd frontend && npm run dev
```

---

## Documentos corporativos (Google Drive)

Los PDFs se descargan desde Google Drive y se clasifican automáticamente:

| Categoría | Subcarpeta | Keywords en nombre |
|---|---|---|
| Políticas | `docs/corporativos/POLITICAS/` | política, politica, código, codigo |
| Procedimientos | `docs/corporativos/PROCEDIMIENTOS/` | procedimiento |
| Reglamentos | `docs/corporativos/REGLAMENTOS/` | reglamento |
| Otros | `docs/corporativos/OTROS/` | (resto) |

Credenciales: carpeta `credentials/` (gitignored). Usar Service Account con permisos de lectura en Drive.

---

## Estado actual del proyecto

| Componente | Estado | Notas |
|---|---|---|
| `data_prep_tool` | ✅ Implementado | Lógica regex local |
| `rag_search_tool` | ✅ Implementado | Conectado a FAISS + embeddings reales via Vertex AI |
| `dlp_anonymizer_tool` | ✅ Implementado | Regex local |
| `AgentExecutor` | ✅ Funcional | Gemini 2.5 Flash (Vertex AI en prod, AI Studio en dev), memoria k=5 |
| Google Drive loader | ✅ Funcional | Service Account + Drive API v3 |
| Backend API (FastAPI) | ✅ Implementado | `api.py` — 4 endpoints, sesiones por `session_id`, CORS |
| GCP SAs + Permisos | ✅ Configurado | `cloudrun-agent-sa` con roles Vertex AI, DLP, Storage, Document AI, Secret Manager |
| Secret Manager | ✅ Configurado | `google-api-key` almacenada, accesible por `cloudrun-agent-sa` |
| Dockerfile | ✅ Implementado | Backend (FastAPI) — `Dockerfile` |
| Dockerfile.job | ✅ Implementado | Ingesta (Document AI) — `Dockerfile.job` |
| Cloud Build | ✅ Configurado | Trigger `build-agente-ia-repo` + `cloudbuild.yaml` (2 imágenes) |
| Despliegue Cloud Run | ✅ Desplegado | `agente-ia-backend` con Vertex AI, Secret Manager, GCS |
| Frontend (Next.js) | ✅ Desplegado | `https://project-genai.vercel.app/` con chat, sesiones, sugerencias |
| CORS | ✅ Configurado | `ALLOWED_ORIGINS` apunta a dominio Vercel |
| Cloud Storage (GCS) | ✅ Implementado | Bucket para PDFs y vectorstore, helpers en `utils/gcs_helpers.py` |
| Document AI | ✅ Configurado | Procesador OCR `ec4388cb0418ca92`, split automático >30 págs |
| Cloud Run Job (ingesta) | ✅ Completado | `ingesta-rag-job` — Document AI + Vertex AI nativo, 454 vectores |
| Pipeline RAG (ingesta) | ✅ Completado | 35 PDFs procesados, índice FAISS en GCS, backend lo descarga auto |
| HyDE | ⬜ Pendiente (Opcional) | Hypothetical Document Embeddings |
| README final | ⬜ Pendiente | Descripción, stack, instrucciones |

---

## Convenciones del código

- **Idioma de comentarios**: Español
- **Docstrings de tools**: En español, descriptivos — el LLM los lee para decidir qué tool usar
- **Nombrado**: snake_case para variables y funciones, UPPER_SNAKE para constantes
- **API keys**: Siempre desde `.env` con `python-dotenv`, nunca hardcodeadas
- **Credenciales**: carpeta `credentials/` (gitignored)
- **Tests**: `python test_agent.py` valida las 3 herramientas

---

## Decisiones de diseño

- **Gemini sobre OpenAI**: Ecosistema GCP coherente (Vertex AI, Cloud DLP, Cloud Run). Gratuito para desarrollo.
- **FAISS sobre Chroma**: Ligero, no requiere servidor, serializable a disco. Ideal para Cloud Run.
- **FastAPI para backend**: Async, automática documentación OpenAPI, ideal para microservicios.
- **Next.js para frontend**: SSR, TypeScript nativo, deploy simple en Vercel.
- **ReAct pattern**: Transparencia en el razonamiento, estándar de LangChain para agentes con tools.
- **Metadata filters**: Permite búsqueda dirigida por categoría/fuente, mejora precisión del RAG.
- **Modelo híbrido LLM**: En desarrollo usa Google AI Studio (API key, gratis). En producción Cloud Run usa Vertex AI (créditos GCP, sin rate limit).
- **langchain_classic**: La migración a langchain 1.2.x requirió cambiar imports de `langchain.agents` → `langchain_classic.agents`.

---

## Cómo extender el proyecto

### Agregar una nueva herramienta

1. Crear `tools/mi_nueva_tool.py` con el decorador `@tool`
2. Escribir un docstring claro en español
3. Importarla en `agent.py` y agregarla a la lista `tools`

### Conectar a GCP real

Ver comentarios `# En producción usar:` en cada tool. Requiere:

- Proyecto GCP con billing habilitado
- `gcloud auth application-default login`
- Variables `GCP_PROJECT_ID` y `GCP_REGION` en `.env`

---

## Checklist de entrega

| Requisito | Estado | Cubierto por |
|---|---|---|
| LangChain en Python | ✅ | `agent.py` — AgentExecutor + ReAct (`langchain_classic`) |
| Al menos 1 agente | ✅ | AgentExecutor con tools y memoria |
| Al menos 2 herramientas propias | ✅ | 3 tools: data_prep, rag_search, dlp_anonymizer |
| API REST (FastAPI) | ✅ | `api.py` — 4 endpoints, sesiones, CORS, Swagger |
| GCP IAM configurado | ✅ | 3 SAs, roles, ADC, Secret Manager |
| RAG sobre base vectorial | ✅ | FAISS + text-embedding-004 (Vertex AI) + Document AI. 454 vectores, 35 PDFs |
| Filtro por metadatos | ✅ | Metadata por chunk: categoria, fuente, pagina, keywords |
| HyDE (opcional) | ⬜ | Pendiente: query → hipótesis → embedding |
| Backend desplegado (Cloud Run) | ✅ | `agente-ia-backend` — Vertex AI + Secret Manager |
| Frontend desplegado (Vercel) | ✅ | `https://project-genai.vercel.app/` — Next.js con chat |
| Seguridad y gobernanza | ✅ | Secret Manager, `.gitignore`, `.dockerignore`, git filter-repo |
| README completo | ⬜ | Pendiente |
