# Servicios, Roles y Permisos GCP — Proyecto Agente IA (s13)

## APIs a habilitar en el proyecto GCP

Habilitar cada API desde **APIs & Services → Library** o con `gcloud`:

#### Desde Cloud Shell / terminal:
```bash
gcloud services enable \
  aiplatform.googleapis.com \
  drive.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  dlp.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com
```

#### Desde la consola GCP:
1. Ve a **APIs & Services → Library** (menú lateral)
2. Busca cada API por nombre (ej: "Vertex AI API")
3. Click en la API → **"Enable"**
4. Repetir para cada API de la tabla

| API | Servicio | Propósito |
|-----|---------|-----------|
| `aiplatform.googleapis.com` | Vertex AI | Embeddings (text-embedding-004) + LLM en prod |
| `drive.googleapis.com` | Google Drive | Descarga de PDFs corporativos |
| `run.googleapis.com` | Cloud Run | Despliegue del backend (FastAPI) |
| `cloudbuild.googleapis.com` | Cloud Build | Build de contenedores Docker |
| `artifactregistry.googleapis.com` | Artifact Registry | Almacén de imágenes Docker |
| `dlp.googleapis.com` | Cloud DLP | Anonimización de PII (producción) |
| `secretmanager.googleapis.com` | Secret Manager | Almacenar API keys y credenciales |
| `iam.googleapis.com` | IAM | Gestión de roles y service accounts |

---

## Service Accounts del proyecto

### Arquitectura de SAs

```
┌──────────────────────────────────────────────────────────────────────┐
│                         PROYECTO GCP                                │
│                                                                      │
│  ┌─────────────────────────┐    ┌──────────────────────────────┐    │
│  │  drive-reader-agemt@... │    │   cloudrun-agent-sa@...      │    │
│  │  (Desarrollo local)     │    │   (Producción - Cloud Run)   │    │
│  ├─────────────────────────┤    ├──────────────────────────────┤    │
│  │ • Vertex AI User        │    │ • Vertex AI User             │    │
│  │ • Drive Viewer (en      │    │ • Cloud DLP User             │    │
│  │   Drive, no IAM)        │    │ • Secret Manager Accessor    │    │
│  │                         │    │ • Drive Viewer (en Drive)    │    │
│  │ Auth: JSON key local    │    │ Auth: Workload Identity      │    │
│  │ o ADC (gcloud auth)     │    │       (automático)           │    │
│  └─────────────────────────┘    └──────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  PROJECT_NUMBER@cloudbuild.gserviceaccount.com       │           │
│  │  (SA default de Cloud Build — NO se crea, ya existe) │           │
│  ├──────────────────────────────────────────────────────┤           │
│  │ • Artifact Registry Writer                           │           │
│  │ • Cloud Run Admin                                    │           │
│  │ • Service Account User                               │           │
│  └──────────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────────┘
```

---

### SA 1: Desarrollo local

| Campo | Valor |
|-------|-------|
| **Nombre** | `drive-reader-agemt` |
| **Email** | `drive-reader-agemt@project-d145b0df-76c9-4324-a6c.iam.gserviceaccount.com` |
| **Uso** | `python agent.py` en tu máquina |
| **Auth** | JSON key (`credentials/service_account.json`) o ADC |

**Roles asignados:**

| Rol | ID | Estado |
|-----|-------|--------|
| Vertex AI User | `roles/aiplatform.user` | ✅ |
| Drive Viewer | *(permiso en Drive, no IAM)* | ✅ |

#### Cómo se asignaron los roles:

**Desde Cloud Shell / terminal:**
```bash
SA_EMAIL=drive-reader-agemt@project-d145b0df-76c9-4324-a6c.iam.gserviceaccount.com

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/aiplatform.user"
```

**Desde la consola GCP:**
1. Ve a **IAM & Admin → IAM**
2. Busca `drive-reader-agemt@...` en la lista
3. Click el **lápiz ✏️** (Edit)
4. Click **"+ Add another role"** → busca `Vertex AI User`
5. **Save**

**Permiso en Drive:**
1. Ve a **Google Drive** → abre la carpeta de PDFs
2. Click **"Compartir"** → pega el email de la SA
3. Asigna rol **"Viewer"** (solo lectura)
4. Confirma

---

### SA 2: Producción (Cloud Run)

| Campo | Valor |
|-------|-------|
| **Nombre** | `cloudrun-agent-sa` |
| **Email** | `cloudrun-agent-sa@project-d145b0df-76c9-4324-a6c.iam.gserviceaccount.com` |
| **Uso** | Backend desplegado en Cloud Run |
| **Auth** | Workload Identity (automático, sin JSON) |

**Roles asignados:**

| Rol | ID | Estado |
|-----|-------|--------|
| Vertex AI User | `roles/aiplatform.user` | ✅ |
| Cloud DLP User | `roles/dlp.user` | ✅ |
| Secret Manager Secret Accessor | `roles/secretmanager.secretAccessor` | ✅ |
| Drive Viewer | *(compartir carpeta en Drive)* | ⬜ Pendiente |

> ⚠️ No olvides compartir la carpeta de Drive con `cloudrun-agent-sa@...` (Viewer) cuando despliegues.

#### Cómo se creó y configuró:

**Desde Cloud Shell / terminal:**
```bash
# Crear la SA
gcloud iam service-accounts create cloudrun-agent-sa \
  --display-name="Cloud Run Agent SA"

# Asignar roles
SA_EMAIL=cloudrun-agent-sa@PROJECT_ID.iam.gserviceaccount.com

for ROLE in \
  roles/aiplatform.user \
  roles/dlp.user \
  roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$ROLE"
done
```

**Desde la consola GCP:**
1. Ve a **IAM & Admin → Service Accounts**
2. Click **"+ Create Service Account"**
3. Nombre: `cloudrun-agent-sa`, click **"Create and Continue"**
4. En "Grant this service account access to project":
   - Busca y agrega: `Vertex AI User`
   - Click **"+ Add another role"** → `Cloud DLP User`
   - Click **"+ Add another role"** → `Secret Manager Secret Accessor`
5. Click **"Done"**

**Permiso en Drive (pendiente para deploy):**
1. Ve a **Google Drive** → carpeta de PDFs corporativos
2. **Compartir** → pega `cloudrun-agent-sa@...iam.gserviceaccount.com`
3. Rol: **Viewer** → Confirmar

---

### SA 3: Cloud Build (automática — no se crea, ya existe)

| Campo | Valor |
|-------|-------|
| **Nombre** | SA default de Cloud Build |
| **Email** | `PROJECT_NUMBER@cloudbuild.gserviceaccount.com` |
| **Uso** | Build Docker + deploy a Cloud Run |
| **Auth** | Automática (GCP la gestiona) |

> Esta SA la crea GCP automáticamente al habilitar Cloud Build. Solo necesitas agregarle roles.

**Roles asignados:**

| Rol | ID | Estado |
|-----|-------|--------|
| Artifact Registry Writer | `roles/artifactregistry.writer` | ✅ |
| Cloud Run Admin | `roles/run.admin` | ✅ |
| Service Account User | `roles/iam.serviceAccountUser` | ✅ |

#### Cómo se asignaron los roles:

**Desde Cloud Shell / terminal:**
```bash
# Obtener el Project Number
PROJECT_NUMBER=$(gcloud projects describe PROJECT_ID --format="value(projectNumber)")
CLOUDBUILD_SA=$PROJECT_NUMBER@cloudbuild.gserviceaccount.com

# Asignar roles
for ROLE in \
  roles/artifactregistry.writer \
  roles/run.admin \
  roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:$CLOUDBUILD_SA" \
    --role="$ROLE"
done
```

**Desde la consola GCP:**
1. Ve a **IAM & Admin → IAM**
2. Marca el checkbox **"Include Google-provided role grants"** (arriba a la derecha)
3. Busca la SA que termina en `@cloudbuild.gserviceaccount.com`
4. Click el **lápiz ✏️** (Edit)
5. Click **"+ Add another role"** → agrega cada rol:
   - `Artifact Registry Writer`
   - `Cloud Run Admin`
   - `Service Account User`
6. **Save**

---

## Notas sobre Organization Policies

La política `iam.disableServiceAccountKeyCreation` estaba bloqueando la creación de JSON keys para SAs.

**Solución aplicada:** Desactivar la política legacy a nivel proyecto.

| Política | Estado |
|----------|--------|
| `iam.disableServiceAccountKeyCreation` (Legacy) | **Not enforced** (desactivada) |
| `iam.managed.disableServiceAccountKeyCreation` (Nueva) | Inactive (no tocar) |

---

## Autenticación para desarrollo local

```bash
# Opción 1: ADC con tu cuenta Google (recomendado)
gcloud auth application-default login
gcloud config set project TU_PROJECT_ID

# Opción 2: SA con JSON key
set GOOGLE_APPLICATION_CREDENTIALS=credentials\service_account.json
```

---

## Próximos pasos (después de permisos)

### 1. Ejecutar ingesta de documentos con Vertex AI

```bash
# Asegurar GCP_PROJECT_ID en .env
python scripts/ingestar_documentos.py
```

Esto usará `text-embedding-004` de Vertex AI para generar embeddings.

### 2. Probar el agente localmente

```bash
python agent.py
```

Ahora usa `ChatGoogleGenerativeAI` con API key (model: `gemini-2.5-flash`).

> **Nota importante:** La cuenta de usuario (`richard.diaz.nahui@gmail.com`) también necesita
> el rol **Vertex AI User** en IAM si se usa Vertex AI para embeddings.
> Tras asignar el rol, ejecutar: `gcloud auth application-default revoke` y luego
> `gcloud auth application-default login --project=PROJECT_ID` para refrescar el token.

### 3. API REST (FastAPI) — ✅ COMPLETADO

Archivo `api.py` implementado con 4 endpoints:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Redirige a Swagger UI (`/docs`) |
| `/api/health` | GET | Health check para Cloud Run |
| `/api/chat` | POST | Enviar pregunta al agente (con `session_id`) |
| `/api/ingest` | POST | Re-ingesta de documentos |

### 4. Containerizar con Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 5. Crear repo en Artifact Registry — ✅ COMPLETADO

**Desde Cloud Shell / terminal:**
```bash
gcloud artifacts repositories create agente-ia-repo \
  --repository-format=docker \
  --location=us-central1 \
  --project=project-d145b0df-76c9-4324-a6c
```

**Desde la consola GCP:**
1. Ve a **Artifact Registry → Repositories**
2. Click **"+ Create Repository"**
3. Nombre: `agente-ia-repo`, Format: `Docker`, Region: `us-central1`
4. Click **"Create"**

---

### 6. Build + Deploy con Cloud Build

Este paso tiene **2 sub-pasos**: construir la imagen Docker y desplegarla en Cloud Run.

#### 6a. Build de la imagen Docker

Sube tu código a Cloud Build, ejecuta el Dockerfile y guarda la imagen en Artifact Registry.

**Desde Cloud Shell / terminal:**

> **Importante:** Ejecutar este comando **dentro del directorio `s13/`** (donde está el Dockerfile).
> Si usas Cloud Shell, primero sube tu código o clona el repo.

```bash
cd s13/

gcloud builds submit \
  --tag us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend \
  --project=project-d145b0df-76c9-4324-a6c
```

**Qué hace este comando:**
1. Empaqueta todo el directorio `s13/` (respetando `.dockerignore`)
2. Lo sube a Cloud Build como un tarball
3. Cloud Build ejecuta el `Dockerfile` paso a paso (instala Python, dependencias, copia código)
4. La imagen resultante se publica en: `us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend`

> El build tarda ~3-5 minutos. Puedes ver el progreso en **Cloud Build → History** en la consola GCP.

**Desde la consola GCP (alternativa manual):**
1. Ve a **Cloud Build → Triggers**
2. Puedes crear un trigger conectado a tu repo Git, o hacer build manual subiendo tu código

**Verificar que la imagen existe:**
```bash
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo
```

#### 6b. Deploy a Cloud Run

Una vez que la imagen está en Artifact Registry, se despliega como servicio en Cloud Run.

**Desde Cloud Shell / terminal:**

```bash
gcloud run deploy agente-ia-backend \
  --image=us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend \
  --service-account=cloudrun-agent-sa@project-d145b0df-76c9-4324-a6c.iam.gserviceaccount.com \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_API_KEY=TU_API_KEY_AQUI,USE_VERTEX_AI=true,GCP_PROJECT_ID=project-d145b0df-76c9-4324-a6c,GCP_REGION=us-central1" \
  --project=project-d145b0df-76c9-4324-a6c
```

**Qué hace cada flag:**

| Flag | Descripción |
|------|-------------|
| `--image=...` | La imagen Docker que construimos en el paso 6a |
| `--service-account=...` | SA de producción con roles de Vertex AI, DLP, Secret Manager |
| `--region=us-central1` | Región donde se despliega el servicio |
| `--allow-unauthenticated` | Permite acceso público (necesario para el frontend) |
| `--set-env-vars=...` | Variables de entorno que reemplazan al `.env` (no se copia al contenedor) |

**Variables de entorno necesarias en Cloud Run:**

| Variable | Valor | Por qué |
|----------|-------|---------|
| `GOOGLE_API_KEY` | `AIzaSyAr6A...` | API key para Gemini 2.5 Flash (LLM) |
| `USE_VERTEX_AI` | `true` | Usar Vertex AI para embeddings (text-embedding-004) |
| `GCP_PROJECT_ID` | `project-d145b0df-76c9-4324-a6c` | Proyecto GCP para Vertex AI |
| `GCP_REGION` | `us-central1` | Región de Vertex AI |

> **Nota:** El `.env` no se copia al contenedor (está en `.dockerignore`). Las variables se pasan
> como env vars del servicio Cloud Run. En producción, usar **Secret Manager** para la API key.

**Desde la consola GCP (alternativa visual):**
1. Ve a **Cloud Run → Create Service**
2. Click **"Select"** → busca la imagen en Artifact Registry (`agente-ia-repo/backend`)
3. Service name: `agente-ia-backend`
4. Region: `us-central1`
5. Authentication: **"Allow unauthenticated invocations"** ✅
6. En **"Container, Networking, Security"** → pestaña **"Container"**:
   - Port: `8080`
7. En pestaña **"Variables & Secrets"** → **"+ Add Variable"**:
   - `GOOGLE_API_KEY` = `(tu API key)`
   - `USE_VERTEX_AI` = `true`
   - `GCP_PROJECT_ID` = `project-d145b0df-76c9-4324-a6c`
   - `GCP_REGION` = `us-central1`
8. En pestaña **"Security"**:
   - Service account: `cloudrun-agent-sa@project-d145b0df-76c9-4324-a6c.iam.gserviceaccount.com`
9. Click **"Create"**

#### Después del deploy

Cloud Run asigna una URL pública al servicio:
```
https://agente-ia-backend-XXXXXXXX-uc.a.run.app
```

**Probar el servicio:**
```bash
# Health check
curl https://agente-ia-backend-XXXXXXXX-uc.a.run.app/api/health

# Swagger UI (abrir en navegador)
https://agente-ia-backend-XXXXXXXX-uc.a.run.app/docs

# Enviar pregunta al agente
curl -X POST https://agente-ia-backend-XXXXXXXX-uc.a.run.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Cuál es la política de teletrabajo?"}'
```

> **⚠️ Sobre la cuota de Vertex AI:** Si el error `429 RESOURCE_EXHAUSTED` persiste en Cloud Run,
> cambiar `USE_VERTEX_AI=false` en las env vars del servicio. Esto usará Google AI Studio (gratis)
> para embeddings en lugar de Vertex AI. Requiere re-ingestar documentos.

---

### 7. Frontend (Next.js → Vercel)

- Crear app Next.js con interfaz de chat
- Conectar al endpoint de Cloud Run (`https://agente-ia-backend-XXXXXXXX-uc.a.run.app`)
- Desplegar en Vercel
- Configurar variable de entorno `NEXT_PUBLIC_API_URL` con la URL de Cloud Run

---

## Costos estimados mensuales (con créditos)

| Servicio | Estimado USD/mes | Notas |
|----------|-----------------|-------|
| Vertex AI (embeddings) | ~$1-5 | text-embedding-004 para RAG |
| Google AI Studio (LLM) | $0 | Gemini 2.5 Flash gratis en dev |
| Vertex AI (LLM prod) | ~$5-15 | Solo en Cloud Run produccion |
| Cloud Run | ~$0-5 | Pay-per-request, free tier generoso |
| Cloud Build | ~$0 | 120 min/día gratis |
| Artifact Registry | ~$0.10 | Por GB almacenado |
| Cloud DLP | ~$1-3 | Por MB procesado |
| **Total estimado** | **~$7-28** | Con uso moderado de desarrollo |

---

## Lecciones aprendidas

| Problema | Causa | Solución |
|---|---|---|
| `ImportError: AgentExecutor` | `langchain` 1.2.x movió clases | Usar `langchain_classic.agents` |
| `404 ChatVertexAI` | Modelo no disponible en publisher | Usar `ChatGoogleGenerativeAI` con API key |
| `429 Rate Limit` | Cuota free tier agotada (gemini-2.0-flash) | Cambiar a `gemini-2.5-flash` (cuota separada) |
| `403 Permission Denied` | Cuenta personal sin rol Vertex AI User | Asignar rol a `user:email` + revocar/renovar ADC |
| `artifacregistry` typo | Error de escritura en API name | `artifactregistry.googleapis.com` (con t) |
| `429 RESOURCE_EXHAUSTED` embeddings | Cuota de Vertex AI para `textembedding-gecko` agotada | Solicitar aumento de cuota en GCP, o usar `USE_VERTEX_AI=false` (Google AI Studio gratis) |
