# Project GenAI — Agente Inteligente con RAG

Solucion de IA generativa que responde preguntas en lenguaje natural sobre documentos corporativos usando Retrieval-Augmented Generation (RAG) y un agente orquestador con LangChain.

**Frontend:** [https://project-genai.vercel.app/](https://project-genai.vercel.app/)
**Backend API:** [https://agente-ia-backend-911975904529.us-central1.run.app/docs](https://agente-ia-backend-911975904529.us-central1.run.app/docs)

---

## Stack Tecnologico

| Capa | Tecnologia |
|------|-----------|
| **LLM** | Gemini 2.5 Flash (Vertex AI) |
| **Embeddings** | text-embedding-004 (Vertex AI, 768 dims) |
| **PDF Extraction** | Document AI (OCR Processor) |
| **Framework** | LangChain (`langchain_classic`) |
| **Vector Store** | FAISS (IndexFlatL2) |
| **Storage** | Google Cloud Storage (GCS) |
| **Ingesta** | Cloud Run Job (Document AI + Vertex AI) |
| **Backend** | FastAPI + Uvicorn (Cloud Run Service) |
| **Frontend** | Next.js / React / TypeScript (Vercel) |
| **Seguridad** | Secret Manager + IAM + Workload Identity |
| **CI/CD** | Cloud Build + Artifact Registry |

---

## Arquitectura

```
Frontend (Vercel)  --->  Cloud Run Service (FastAPI + Agente ReAct)
                              |
                              |  descarga FAISS index
                              v
                         Cloud Storage (GCS)
                              ^
                              |  sube FAISS index
                              |
                         Cloud Run Job (Document AI + Embeddings)
                              |
                              |  lee PDFs
                              v
                         Cloud Storage (GCS) /pdfs/
```

Ver [ARQUITECTURA.md](ARQUITECTURA.md) para diagramas detallados.

---

## Estructura del Codigo

```
project_genai/
├── agent.py                  # Agente principal (ReAct + LangChain)
├── api.py                    # FastAPI — POST /api/chat, GET /api/health
├── test_agent.py             # Suite de pruebas
├── requirements.txt          # Dependencias Python
├── Dockerfile                # Imagen backend (Cloud Run Service)
├── Dockerfile.job            # Imagen ingesta (Cloud Run Job)
├── cloudbuild.yaml           # CI/CD — construye 2 imagenes
│
├── tools/
│   ├── data_prep.py          # Tool 1: limpieza texto -> JSONL
│   ├── rag_search.py         # Tool 2: busqueda semantica FAISS
│   ├── dlp_anonymizer.py     # Tool 3: anonimizacion PII
│   ├── pdf_processor.py      # Extraccion de PDFs (local)
│   └── drive_loader.py       # Descarga desde Google Drive
│
├── scripts/
│   └── ingestar_documentos.py  # Pipeline ingesta (Document AI)
│
├── utils/
│   └── gcs_helpers.py        # Operaciones GCS
│
├── config/
│   └── settings.py           # Configuracion centralizada
│
├── frontend/                 # Next.js app (Vercel)
│   └── app/
│       ├── page.tsx
│       └── components/
│           └── chat.tsx      # Componente de chat
│
└── docs/
    └── GCP_SERVICIOS_Y_PERMISOS.md  # Guia completa GCP
```

---

## Instalacion y Ejecucion Local

### Prerequisitos

- Python 3.12+
- Node.js 18+ (para frontend)
- API key de Google AI Studio ([obtener aqui](https://aistudio.google.com/app/apikeys))

### Backend

```bash
# Clonar repositorio
git clone https://github.com/Richard2735/project_genai.git
cd project_genai

# Crear entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tu GOOGLE_API_KEY

# Ejecutar el agente en modo conversacion
python agent.py

# O ejecutar la API
uvicorn api:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Editar .env.local: NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
# Abrir http://localhost:3000
```

---

## Despliegue en GCP

### 1. Configurar proyecto GCP

```bash
# Habilitar APIs necesarias
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  documentai.googleapis.com
```

### 2. Crear Service Account

```bash
gcloud iam service-accounts create cloudrun-agent-sa \
  --display-name="Cloud Run Agent SA"

SA_EMAIL=cloudrun-agent-sa@$(gcloud config get-value project).iam.gserviceaccount.com

for ROLE in roles/aiplatform.user roles/dlp.user \
  roles/secretmanager.secretAccessor roles/storage.objectAdmin \
  roles/documentai.apiUser; do
  gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="serviceAccount:$SA_EMAIL" --role="$ROLE"
done
```

### 3. Crear procesador Document AI

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{"type": "OCR_PROCESSOR", "displayName": "pdf-extractor-rag"}' \
  "https://us-documentai.googleapis.com/v1/projects/$(gcloud config get-value project)/locations/us/processors"
```

### 4. Subir PDFs a Cloud Storage

```bash
BUCKET_NAME=genai-docs-$(gcloud config get-value project)

gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --location=us-central1 --uniform-bucket-level-access --public-access-prevention

gcloud storage cp -r docs/corporativos/POLITICAS/ "gs://${BUCKET_NAME}/pdfs/POLITICAS/"
gcloud storage cp -r docs/corporativos/PROCEDIMIENTOS/ "gs://${BUCKET_NAME}/pdfs/PROCEDIMIENTOS/"
gcloud storage cp -r docs/corporativos/REGLAMENTOS/ "gs://${BUCKET_NAME}/pdfs/REGLAMENTOS/"
```

### 5. Build y deploy

```bash
# Construir imagenes (backend + ingesta-job)
gcloud builds submit --config=cloudbuild.yaml .

# Desplegar backend
gcloud run deploy agente-ia-backend \
  --image=us-central1-docker.pkg.dev/$(gcloud config get-value project)/agente-ia-repo/backend \
  --service-account=$SA_EMAIL \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-secrets="GOOGLE_API_KEY=google-api-key:latest" \
  --set-env-vars="USE_VERTEX_AI=true,GCP_PROJECT_ID=$(gcloud config get-value project),GCP_REGION=us-central1,GCS_BUCKET_NAME=$BUCKET_NAME,GCS_VECTORSTORE_PREFIX=vectorstore/,FAISS_INDEX_DIR=/tmp/vectorstore"

# Ejecutar ingesta
gcloud run jobs create ingesta-rag-job \
  --image=us-central1-docker.pkg.dev/$(gcloud config get-value project)/agente-ia-repo/ingesta-job \
  --service-account=$SA_EMAIL \
  --region=us-central1 \
  --memory=2Gi --cpu=2 --task-timeout=30m \
  --set-env-vars="GCP_PROJECT_ID=$(gcloud config get-value project),GCS_BUCKET_NAME=$BUCKET_NAME,DOCAI_PROCESSOR_ID=<tu_processor_id>,DOCAI_LOCATION=us,GCS_VECTORSTORE_PREFIX=vectorstore/,FAISS_INDEX_DIR=/tmp/vectorstore" \
  --set-secrets="GOOGLE_API_KEY=google-api-key:latest"

gcloud run jobs execute ingesta-rag-job --region=us-central1
```

### 6. Frontend en Vercel

1. Importar repo en [vercel.com](https://vercel.com)
2. Root Directory: `frontend`
3. Variable de entorno: `NEXT_PUBLIC_API_URL` = URL de Cloud Run

---

## Como Probar el Agente

### Desde el frontend

1. Ir a [https://project-genai.vercel.app/](https://project-genai.vercel.app/)
2. Escribir una pregunta sobre documentos corporativos:
   - "Cual es la politica de seguridad de la informacion?"
   - "Que dice el reglamento interno sobre vacaciones?"
   - "Resume el procedimiento de gestion de incidentes"

### Desde la API directamente

```bash
# Health check
curl https://agente-ia-backend-911975904529.us-central1.run.app/api/health

# Preguntar al agente
curl -X POST https://agente-ia-backend-911975904529.us-central1.run.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Cual es la politica de teletrabajo?", "session_id": "test"}'
```

### Ejecutar tests

```bash
python test_agent.py
```

---

## Las 3 Herramientas del Agente

| # | Tool | Que hace | Ejemplo de uso |
|---|------|---------|----------------|
| 1 | `data_prep_tool` | Limpia texto crudo (HTML, caracteres especiales) y lo convierte a JSONL | "Limpia este HTML y conviertelo a formato de entrenamiento" |
| 2 | `rag_search_tool` | Busca fragmentos relevantes en documentos corporativos usando similitud semantica | "Cual es la politica de seguridad?" |
| 3 | `dlp_anonymizer_tool` | Detecta y enmascara PII (emails, telefonos, DNI, tarjetas) | "Anonimiza: juan@email.com tiene DNI 12345678" |

---

## Pipeline RAG

```
PDFs (GCS) --> Document AI (OCR) --> Fragmentacion --> Embeddings (text-embedding-004) --> FAISS --> GCS
                                                                                                    |
Query usuario --> Embedding query --> FAISS search (Top-K) --> Chunks relevantes --> LLM --> Respuesta
```

- **35 PDFs** corporativos procesados (politicas, procedimientos, reglamentos)
- **454 vectores** en indice FAISS
- **768 dimensiones** por vector (text-embedding-004)
- Metadata por chunk: categoria, fuente, pagina

---

## Documentacion Adicional

- [ARQUITECTURA.md](ARQUITECTURA.md) — Diagramas de arquitectura completos
- [CLAUDE.md](CLAUDE.md) — Contexto del proyecto y decisiones de diseno
- [docs/GCP_SERVICIOS_Y_PERMISOS.md](docs/GCP_SERVICIOS_Y_PERMISOS.md) — Guia completa de configuracion GCP
