# Arquitectura del Sistema — Proyecto Final IA Generativa

## 1. Arquitectura de produccion (vista completa)

```
┌─────────────────────┐     HTTPS      ┌──────────────────────────────┐
│   Frontend (Vercel)  │ ──────────────>│  Cloud Run Service           │
│   Next.js / React    │<──────────────│  agente-ia-backend           │
│                      │               │                              │
│ - Caja de texto      │               │  POST /api/chat              │
│ - Respuesta modelo   │               │  POST /api/ingest            │
│ - Historial chat     │               │  GET  /api/health            │
│ - Sesiones           │               │  GET  /docs (Swagger)        │
│ - Sugerencias        │               │                              │
│                      │               │  AgentExecutor (ReAct)       │
│ project-genai.       │               │  ├── Gemini 2.5 Flash        │
│   vercel.app         │               │  │   (Vertex AI)             │
│                      │               │  ├── Memoria (k=5)           │
└─────────────────────┘               │  └── Tools:                  │
                                       │       ├── data_prep_tool     │
                                       │       ├── rag_search_tool    │
                                       │       └── dlp_anonymizer     │
                                       │                              │
                                       │  Al iniciar:                 │
                                       │  GCS -> descarga FAISS index │
                                       │  -> carga en memoria         │
                                       └──────────┬───────────────────┘
                                                  │ lee vectorstore/
                                                  v
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
                                                  ^ escribe vectorstore/
                                                  │ lee pdfs/
                                       ┌──────────┴───────────────────┐
                                       │  Cloud Run Job               │
                                       │  ingesta-rag-job             │
                                       │  (2 GB RAM, 2 vCPU, 30m)    │
                                       │  Imagen: ingesta-job         │
                                       │  (Dockerfile.job)            │
                                       │                              │
                                       │  1. Descarga PDFs de GCS     │
                                       │  2. Extrae texto con         │
                                       │     Document AI (OCR)        │
                                       │  3. Fragmenta texto          │
                                       │  4. Genera embeddings        │
                                       │     (Vertex AI text-emb-004) │
                                       │  5. Construye indice FAISS   │
                                       │  6. Sube indice a GCS        │
                                       └──────────────────────────────┘
```

## 2. Principios de la arquitectura

| Principio | Implementacion |
|---|---|
| **Stateless containers** | Contenedores no guardan estado; todo persiste en GCS |
| **Separacion compute/storage** | PDFs e indice en GCS, procesamiento en Cloud Run |
| **Minimo privilegio** | SA `cloudrun-agent-sa` con solo los roles necesarios |
| **Inmutabilidad** | Imagenes Docker versionadas en Artifact Registry |
| **Batch vs Serving** | Job para ingesta pesada, Service para consultas en tiempo real |
| **2 imagenes Docker** | `backend` (FastAPI) y `ingesta-job` (Document AI + embeddings) |

## 3. Flujo del agente (ReAct Pattern)

```
┌─────────────────────────────────────────────────────────────────┐
│                         USUARIO                                 │
│                    (Escribe pregunta)                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────────────┐
│                     INPUT PROCESSING                            │
│                                                                 │
│  1. Recibir prompt del usuario (via API /api/chat)             │
│  2. Recuperar historial de memoria (ultimos 5 turnos)          │
│  3. Construir contexto para el LLM                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────────────┐
│              LLM REASONING (Gemini 2.5 Flash)                  │
│              (Vertex AI en prod / AI Studio en dev)             │
│                                                                 │
│  Analizando docstrings de tools disponibles:                   │
│  - data_prep_tool:        "Limpia texto crudo a JSONL"         │
│  - rag_search_tool:       "Busca en documentos corporativos"   │
│  - dlp_anonymizer_tool:   "Enmascara PII"                      │
│                                                                 │
│  Razonamiento ReAct: THINK -> ACT -> OBSERVE -> (loop)         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────────────┐
│                    TOOL EXECUTION                               │
│                                                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐  │
│  │  data_prep    │  │  rag_search   │  │  dlp_anonymizer   │  │
│  │  ────────     │  │  ──────────   │  │  ──────────────   │  │
│  │  Limpia HTML  │  │  FAISS search │  │  Detecta PII      │  │
│  │  Normaliza    │  │  + metadata   │  │  Enmascara        │  │
│  │  -> JSONL     │  │  filters      │  │  emails, DNI,     │  │
│  │               │  │  Top-K chunks │  │  telefonos, etc.  │  │
│  └───────────────┘  └───────────────┘  └───────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────────────┐
│               MEMORY UPDATE & OUTPUT                            │
│                                                                 │
│  1. Guardar en memoria (ventana k=5)                           │
│  2. Devolver respuesta al usuario via API                      │
└─────────────────────────────────────────────────────────────────┘
```

## 4. Pipeline RAG (Retrieval-Augmented Generation)

### 4.1 Flujo de ingesta (Cloud Run Job)

```
Google Cloud Storage          Document AI             Text Splitter
┌──────────────┐         ┌──────────────────┐     ┌─────────────────┐
│ PDFs en GCS  │────────>│ OCR avanzado     │────>│ Chunks 500 char │
│ /pdfs/...    │         │ (procesador OCR) │     │ overlap 100     │
└──────────────┘         │ Split >30 pags   │     └────────┬────────┘
                         └──────────────────┘              │
                                                           v
                         Vertex AI                    FAISS Index
                    ┌──────────────────┐         ┌─────────────────┐
                    │ text-embedding   │         │ IndexFlatL2     │
                    │ -004 (768 dims)  │────────>│ + InMemoryDoc   │
                    │ SDK nativo       │         │ store           │
                    │ (no aiplatform)  │         │ -> GCS          │
                    └──────────────────┘         └─────────────────┘

Metadata por chunk:
  - categoria: POLITICAS | PROCEDIMIENTOS | REGLAMENTOS | OTROS
  - fuente: nombre_archivo.pdf
  - pagina: numero de pagina
```

### 4.2 Flujo de consulta (Cloud Run Service)

```
Query usuario --> Embedding query (Vertex AI) --> FAISS search (Top-K)
                                                       │
                                                       v
                                                  Chunks relevantes
                                                  + metadata
                                                       │
                                                       v
                                                  LLM (Gemini 2.5 Flash)
                                                       │
                                                       v
                                                  Respuesta final
                                                  con fuentes citadas
```

## 5. Las 3 herramientas del agente

```
┌──────────────────────────────────────────────────────────────┐
│                    TOOLS DEL AGENTE                          │
└──────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        v                  v                  v
   ┌──────────┐      ┌──────────┐      ┌──────────────┐
   │ Tool 1   │      │ Tool 2   │      │ Tool 3       │
   │ data_prep│      │ rag_     │      │ dlp_         │
   │ _tool    │      │ search_  │      │ anonymizer_  │
   │          │      │ tool     │      │ tool         │
   ├──────────┤      ├──────────┤      ├──────────────┤
   │Entrada:  │      │Entrada:  │      │Entrada:      │
   │raw_text  │      │query     │      │text (con PII)│
   ├──────────┤      ├──────────┤      ├──────────────┤
   │Proceso:  │      │Proceso:  │      │Proceso:      │
   │- Limpia  │      │- Embedding│     │- Detecta PII │
   │  HTML    │      │- FAISS   │      │- Enmascara   │
   │- Normaliz│      │  search  │      │  emails, DNI │
   │- JSONL   │      │- Top-K   │      │  telefonos   │
   ├──────────┤      ├──────────┤      ├──────────────┤
   │Salida:   │      │Salida:   │      │Salida:       │
   │JSONL     │      │Documentos│      │Texto         │
   │limpio    │      │relevantes│      │anonimizado   │
   └──────────┘      └──────────┘      └──────────────┘
```

| Tool | Archivo | Cuando se usa | En produccion |
|------|---------|---------------|---------------|
| `data_prep_tool` | `tools/data_prep.py` | "Limpia este HTML", "convierte a JSONL" | Cloud Dataflow + BigQuery ML |
| `rag_search_tool` | `tools/rag_search.py` | "Cual es la politica de...", "busca en documentos" | FAISS + Vertex AI Embeddings |
| `dlp_anonymizer_tool` | `tools/dlp_anonymizer.py` | "Anonimiza este texto", "protege datos sensibles" | Cloud DLP API |

## 6. Infraestructura GCP

### Service Accounts

```
┌──────────────────────────────────────────────────────────────┐
│                      PROYECTO GCP                            │
│                                                              │
│  ┌─────────────────────────┐   ┌──────────────────────────┐ │
│  │  drive-reader-agemt@... │   │  cloudrun-agent-sa@...   │ │
│  │  (Desarrollo local)     │   │  (Produccion)            │ │
│  ├─────────────────────────┤   ├──────────────────────────┤ │
│  │ - Vertex AI User        │   │ - Vertex AI User         │ │
│  │ - Drive Viewer          │   │ - Cloud DLP User         │ │
│  │                         │   │ - Secret Manager Access  │ │
│  │ Auth: JSON key / ADC    │   │ - Storage Object Admin   │ │
│  └─────────────────────────┘   │ - Document AI API User   │ │
│                                │                          │ │
│                                │ Auth: Workload Identity  │ │
│                                └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Imagenes Docker (Artifact Registry)

```
agente-ia-repo/
├── backend          <-- Cloud Run Service (Dockerfile)
│   CMD: uvicorn api:app
│   Contiene: FastAPI + LangChain + agente completo
│
└── ingesta-job      <-- Cloud Run Job (Dockerfile.job)
    CMD: python scripts/ingestar_documentos.py
    Contiene: Document AI + embeddings (sin aiplatform pesado)
```

### Cloud Build (cloudbuild.yaml)

```
Un solo build construye ambas imagenes:

Step 1: docker build -t .../backend .           (Dockerfile)
Step 2: docker build -f Dockerfile.job -t .../ingesta-job .  (Dockerfile.job)
```

## 7. Estructura del codigo

```
project_genai/
├── agent.py               <-- Punto de entrada (python agent.py)
├── api.py                 <-- FastAPI server (4 endpoints)
├── test_agent.py          <-- Suite de pruebas
├── requirements.txt       <-- Dependencias Python (unico para todo)
├── Dockerfile             <-- Imagen backend (Cloud Run Service)
├── Dockerfile.job         <-- Imagen ingesta (Cloud Run Job)
├── cloudbuild.yaml        <-- Build de ambas imagenes
├── ARQUITECTURA.md        <-- Este archivo
├── CLAUDE.md              <-- Contexto completo del proyecto
├── .env / .env.example    <-- Variables de entorno
├── .gitignore / .dockerignore
│
├── tools/
│   ├── data_prep.py       <-- Tool 1: limpieza y JSONL
│   ├── rag_search.py      <-- Tool 2: busqueda semantica FAISS
│   ├── dlp_anonymizer.py  <-- Tool 3: anonimizacion PII
│   ├── pdf_processor.py   <-- Extraccion de PDFs (local)
│   └── drive_loader.py    <-- Descarga desde Google Drive
│
├── scripts/
│   ├── ingestar_documentos.py  <-- Pipeline de ingesta (Document AI)
│   └── descargar_pdfs.py       <-- Descarga PDFs desde Drive
│
├── utils/
│   └── gcs_helpers.py     <-- Operaciones GCS (subir/bajar)
│
├── config/
│   └── settings.py        <-- Configuracion centralizada
│
├── frontend/              <-- Next.js app (Vercel)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── components/
│   │       └── chat.tsx   <-- Componente de chat
│   └── .env.local         <-- NEXT_PUBLIC_API_URL
│
├── interface/             <-- Streamlit (desarrollo local)
│   └── app.py
│
├── docs/
│   ├── corporativos/      <-- PDFs clasificados
│   └── GCP_SERVICIOS_Y_PERMISOS.md
│
├── credentials/           <-- Service Account JSON (gitignored)
└── vectorstore/           <-- Indice FAISS local (gitignored)
```

## 8. Stack tecnologico

| Capa | Tecnologia | Uso |
|------|-----------|-----|
| **LLM** | Gemini 2.5 Flash (Vertex AI) | Generacion de respuestas + ReAct reasoning |
| **Embeddings** | text-embedding-004 (Vertex AI) | Vectorizacion de documentos para RAG |
| **Framework** | LangChain (`langchain_classic`) | Agente, tools, cadenas RAG, memoria |
| **Vector Store** | FAISS (IndexFlatL2) | Almacenamiento y busqueda de embeddings |
| **PDF Extraction** | Document AI (OCR Processor) | Extraccion de texto con OCR avanzado |
| **Object Storage** | Cloud Storage (GCS) | PDFs corporativos + indice FAISS persistido |
| **Batch Processing** | Cloud Run Jobs | Ingesta masiva de documentos |
| **Backend API** | FastAPI + Uvicorn | API REST del agente como microservicio |
| **Frontend** | Next.js / React (TypeScript) | Interfaz de consulta web |
| **Anonimizacion** | Regex local / Cloud DLP | Enmascaramiento de PII |
| **CI/CD** | Cloud Build + Artifact Registry | Build automatico de imagenes Docker |
| **Despliegue backend** | Cloud Run Service | Backend como contenedor Docker |
| **Despliegue frontend** | Vercel | Frontend web |
| **Seguridad** | Secret Manager + IAM | API keys cifradas + minimo privilegio |

## 9. URLs de produccion

| Servicio | URL |
|----------|-----|
| **Frontend** | `https://project-genai.vercel.app/` |
| **Backend API** | `https://agente-ia-backend-911975904529.us-central1.run.app` |
| **Health Check** | `https://agente-ia-backend-911975904529.us-central1.run.app/api/health` |
| **Swagger UI** | `https://agente-ia-backend-911975904529.us-central1.run.app/docs` |

## 10. Ciclo de vida del AgentExecutor

```
┌─────────────────────────────────────────────────────┐
│         agent_executor.invoke()                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. INPUT                                          │
│     └-> Recibe {"input": "pregunta", "session_id"} │
│                                                     │
│  2. MEMORY RETRIEVAL                               │
│     └-> Obtiene ultimos 5 turnos de la sesion      │
│                                                     │
│  3. CONTEXT BUILDING                               │
│     └-> Construye prompt con contexto + pregunta   │
│                                                     │
│  4. LLM CALL                                       │
│     └-> Envia a Gemini 2.5 Flash (Vertex AI)       │
│                                                     │
│  5. TOOL SELECTION                                 │
│     └-> LLM decide que tool usar                   │
│                                                     │
│  6. LOOP (hasta max_iterations=5)                  │
│     ├-> TOOL EXECUTION                             │
│     │   └-> Ejecuta tool seleccionada              │
│     │                                              │
│     ├-> OBSERVATION                                │
│     │   └-> LLM observa resultado                  │
│     │                                              │
│     └-> DECISION                                   │
│         ├-> Responder?  -> Final answer            │
│         ├-> Otra tool?  -> Volver a step 5         │
│         └-> Error?      -> handle_parsing_errors   │
│                                                     │
│  7. MEMORY UPDATE                                  │
│     └-> Guarda user input + respuesta en memory    │
│                                                     │
│  8. OUTPUT                                         │
│     └-> Retorna {"output": "respuesta final"}      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 11. Matriz de decision: cuando usar cada tool

| Situacion | Tool | Por que |
|-----------|------|--------|
| "Limpia este HTML" | data_prep_tool | Docstring: "Limpia texto crudo" |
| "Cual es la politica de...?" | rag_search_tool | Docstring: "Busca documentos corporativos" |
| "Anonimiza este email" | dlp_anonymizer_tool | Docstring: "Enmascara PII" |
| "Convierte a JSONL" | data_prep_tool | Docstring: "formato JSONL" |
| "Que dice el reglamento?" | rag_search_tool | Docstring: "documento interno" |
| "Protege DNI y telefonos" | dlp_anonymizer_tool | Docstring: "detecta PII" |
