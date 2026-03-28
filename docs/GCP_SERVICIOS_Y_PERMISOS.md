# Servicios, Roles y Permisos GCP — Proyecto Agente IA (project_genai)

## APIs a habilitar en el proyecto GCP

Habilitar cada API desde **APIs & Services → Library** o con `gcloud`:

#### Desde Cloud Shell / terminal

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

#### Desde la consola GCP

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

#### Cómo se asignaron los roles

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

#### Cómo se creó y configuró

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

#### Cómo se asignaron los roles

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

### 1. Ejecutar ingesta de documentos con Vertex AI (desde Cloud Shell)

**Prerequisitos:**

```bash
# 1. Autenticarse (obligatorio si la sesión se reinició)
gcloud auth application-default login

# 2. Asegurar que el .env tiene las variables correctas
cat .env
# Debe tener: USE_VERTEX_AI=true, GCP_PROJECT_ID=..., GCP_REGION=us-central1

# 3. Verificar que los PDFs están en docs/corporativos/
ls docs/corporativos/POLITICAS/ docs/corporativos/PROCEDIMIENTOS/ docs/corporativos/REGLAMENTOS/
```

**Ejecutar la ingesta:**

```bash
python scripts/ingestar_documentos.py
```

**¿Qué hace el script?**

1. Lee cada PDF de `docs/corporativos/` (35 PDFs, ~820 páginas)
2. Fragmenta el texto en chunks de ~500 caracteres con overlap de 100
3. Genera embeddings con `text-embedding-004` via Vertex AI
4. Almacena todo en un índice FAISS en `vectorstore/`

**Optimizaciones implementadas (para Cloud Shell con ~1.7 GB RAM):**

| Optimización | Por qué |
|---|---|
| Procesa 1 PDF a la vez | Evita cargar todos los fragmentos en memoria |
| Batch size de 5 | Menos presión en RAM y API |
| `gc.collect()` después de cada PDF | Fuerza liberación de memoria |
| Checkpoint cada 5 PDFs | Guarda índice a disco, borra de RAM, recarga limpio |
| Reintentos con backoff (2, 4, 8, 16, 32s) | Maneja error 429 RESOURCE_EXHAUSTED de Vertex AI |
| Pausa de 2s entre lotes | Respeta rate limits de la API |

**Después de la ingesta exitosa:**

```bash
# Verificar que el índice se creó
ls -la vectorstore/
# Debe contener: index.faiss, index.pkl

# Reconstruir imagen Docker con el vectorstore incluido
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend \
  --project=project-d145b0df-76c9-4324-a6c

# Redesplegar Cloud Run con la nueva imagen
gcloud run deploy agente-ia-backend \
  --image=us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend \
  --service-account=cloudrun-agent-sa@project-d145b0df-76c9-4324-a6c.iam.gserviceaccount.com \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-secrets="GOOGLE_API_KEY=google-api-key:latest" \
  --set-env-vars="USE_VERTEX_AI=true,GCP_PROJECT_ID=project-d145b0df-76c9-4324-a6c,GCP_REGION=us-central1,ALLOWED_ORIGINS=https://project-genai.vercel.app" \
  --project=project-d145b0df-76c9-4324-a6c
```

### 2. Probar el agente localmente

```bash
python agent.py
```

Usa `ChatVertexAI` (Vertex AI) o `ChatGoogleGenerativeAI` (AI Studio) según `USE_VERTEX_AI` en `.env`.

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

> **Importante:** Ejecutar este comando **dentro del directorio `project_genai/`** (donde está el Dockerfile).
> Si usas Cloud Shell, primero sube tu código o clona el repo.

```bash
cd project_genai/

gcloud builds submit \
  --tag us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend \
  --project=project-d145b0df-76c9-4324-a6c
```

**Qué hace este comando:**

1. Empaqueta todo el directorio `project_genai/` (respetando `.dockerignore`)
2. Lo sube a Cloud Build como un tarball
3. Cloud Build ejecuta el `Dockerfile` paso a paso (instala Python, dependencias, copia código)
4. La imagen resultante se publica en: `us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend`

> El build tarda ~3-5 minutos. Puedes ver el progreso en **Cloud Build → History** en la consola GCP.

**Desde la consola GCP (alternativa manual — 1ra Generación):**

> **¿1ra Gen vs 2da Gen?** Ambas funcionan para este proyecto. La 1ra Gen es más simple de configurar (conexión OAuth directa). La 2da Gen requiere pasar primero por **Cloud Build → Repositories**. Para desarrollo, usa 1ra Gen.

#### Paso 1: Conectar el repositorio GitHub

1. Ve a **Cloud Build → Triggers**
2. Click **"Connect Repository"**
3. Selecciona **"GitHub (Cloud Build GitHub App)"**
4. Autoriza la app de Cloud Build en GitHub
5. Selecciona tu repositorio → **"Connect"**

#### Paso 2: Crear el Trigger

1. Click **"Create Trigger"**
2. Completa los campos:

| Campo | Valor |
|-------|-------|
| **Name** | `build-backend` |
| **Region** | `us-central1` |
| **Event** | ☑ Push to a branch |
| **Branch** | `^main$` |
| **Configuration** | ☑ Cloud Build configuration file (yaml or json) |
| **Config file location** | `project_genai/cloudbuild.yaml` |
| **Service account** | Reutilizar SA existente (ver nota abajo) |

1. Todo lo demás se deja por **defecto** → Click **"Create"**

> **Nota sobre Service Account en el Trigger:** Si ya tienes una SA con los roles `cloudbuild.builds.editor`, `artifactregistry.writer`, `logging.logWriter` y `storage.objectViewer`, puedes reutilizarla. Verifica sus roles con:

```bash
gcloud projects get-iam-policy project-d145b0df-76c9-4324-a6c \
  --flatten="bindings[].members" \
  --filter="bindings.members:TU_SA@project-d145b0df-76c9-4324-a6c.iam.gserviceaccount.com" \
  --format="table(bindings.role)"
```

#### Paso 3: Crear `cloudbuild.yaml` en `project_genai/`

Cloud Build necesita este archivo para saber qué construir:

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend'
      - '.'

images:
  - 'us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend'
```

#### Activar el build manualmente (sin esperar un push)

1. Ve a **Cloud Build → Triggers**
2. Busca tu trigger `build-backend`
3. Click **"Run"** → selecciona la rama `main` → **"Run Trigger"**

**Verificar que la imagen existe:**

```bash
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo
```

#### 6b. Crear secreto en Secret Manager (Gobernanza de datos)

Antes de desplegar, almacenamos la API key en **Secret Manager** para que nunca quede
expuesta como texto plano en la configuración de Cloud Run.

> **¿Por qué Secret Manager?** Las env vars en texto plano son visibles para cualquiera con
> acceso al servicio en la consola GCP. Secret Manager cifra el valor, controla acceso por IAM,
> y permite rotar keys sin redesplegar.

**Desde Cloud Shell / terminal:**

```bash
# Crear el secreto con la API key
# Reemplaza TU_NUEVA_API_KEY con tu key real (obtenida en aistudio.google.com/app/apikeys)
echo -n "TU_NUEVA_API_KEY" | gcloud secrets create google-api-key \
  --data-file=- \
  --replication-policy=automatic \
  --project=project-d145b0df-76c9-4324-a6c
```

**Qué hace este comando:**

1. Crea un secreto llamado `google-api-key` en Secret Manager
2. El valor es tu API key de Google AI Studio
3. `--replication-policy=automatic` replica el secreto en múltiples regiones (alta disponibilidad)
4. El valor se cifra en reposo con claves gestionadas por Google

**Verificar que el secreto se creó:**

```bash
gcloud secrets list --project=project-d145b0df-76c9-4324-a6c
```

**Desde la consola GCP:**

1. Ve a **Security → Secret Manager** (menú lateral)
2. Click **"+ Create Secret"**
3. Nombre: `google-api-key`
4. Secret value: pega tu API key
5. Replication: **"Automatic"** (dejar por defecto)
6. Click **"Create Secret"**

**Verificar acceso de la SA:**

La SA `cloudrun-agent-sa` ya tiene el rol `Secret Manager Secret Accessor` (configurado en el paso de SAs).
Para verificar:

```bash
gcloud secrets get-iam-policy google-api-key \
  --project=project-d145b0df-76c9-4324-a6c
```

Si el rol no aparece, agregarlo manualmente:

```bash
gcloud secrets add-iam-policy-binding google-api-key \
  --member="serviceAccount:cloudrun-agent-sa@project-d145b0df-76c9-4324-a6c.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=project-d145b0df-76c9-4324-a6c
```

**Desde la consola GCP (verificar/agregar acceso):**

1. Ve a **Secret Manager → `google-api-key`**
2. Pestaña **"Permissions"**
3. Verifica que `cloudrun-agent-sa@...` tenga `Secret Manager Secret Accessor`
4. Si no aparece: click **"Grant Access"** → pega el email de la SA → rol `Secret Manager Secret Accessor` → **Save**

---

#### 6c. Deploy a Cloud Run

Una vez que la imagen está en Artifact Registry y el secreto en Secret Manager,
se despliega como servicio en Cloud Run.

**Desde Cloud Shell / terminal:**

```bash
gcloud run deploy agente-ia-backend \
  --image=us-central1-docker.pkg.dev/project-d145b0df-76c9-4324-a6c/agente-ia-repo/backend \
  --service-account=cloudrun-agent-sa@project-d145b0df-76c9-4324-a6c.iam.gserviceaccount.com \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-secrets="GOOGLE_API_KEY=google-api-key:latest" \
  --set-env-vars="USE_VERTEX_AI=true,GCP_PROJECT_ID=project-d145b0df-76c9-4324-a6c,GCP_REGION=us-central1" \
  --project=project-d145b0df-76c9-4324-a6c
```

**Qué hace cada flag:**

| Flag | Descripción |
|------|-------------|
| `--image=...` | La imagen Docker que construimos en el paso 6a |
| `--service-account=...` | SA de producción con roles de Vertex AI, DLP, Secret Manager |
| `--region=us-central1` | Región donde se despliega el servicio |
| `--allow-unauthenticated` | Permite acceso público (necesario para el frontend) |
| `--set-secrets=...` | Inyecta secretos de Secret Manager como env vars (cifrados, no en texto plano) |
| `--set-env-vars=...` | Variables de entorno no sensibles |

**Variables de entorno del servicio:**

| Variable | Origen | Valor | Por qué |
|----------|--------|-------|---------|
| `GOOGLE_API_KEY` | **Secret Manager** (`google-api-key:latest`) | Cifrado | API key para Gemini 2.5 Flash (LLM) |
| `USE_VERTEX_AI` | Env var | `true` | Usar Vertex AI para embeddings (text-embedding-004) |
| `GCP_PROJECT_ID` | Env var | `project-d145b0df-76c9-4324-a6c` | Proyecto GCP para Vertex AI |
| `GCP_REGION` | Env var | `us-central1` | Región de Vertex AI |

> **Nota:** El `.env` no se copia al contenedor (está en `.dockerignore`).
> La API key se inyecta desde Secret Manager en runtime — nunca queda expuesta en la config.
> Las demás variables (no sensibles) se pasan como env vars normales.

**Desde la consola GCP (alternativa visual):**

1. Ve a **Cloud Run → Create Service**
2. Click **"Select"** → busca la imagen en Artifact Registry (`agente-ia-repo/backend`)
3. Service name: `agente-ia-backend`
4. Region: `us-central1`
5. Authentication: **"Allow unauthenticated invocations"** ✅
6. En **"Container, Networking, Security"** → pestaña **"Container"**:
   - Port: `8080`
7. En pestaña **"Variables & Secrets"**:
   - Click **"+ Add Variable"** (para env vars normales):
     - `USE_VERTEX_AI` = `true`
     - `GCP_PROJECT_ID` = `project-d145b0df-76c9-4324-a6c`
     - `GCP_REGION` = `us-central1`
   - Click **"+ Reference a Secret"** (para la API key):
     - Name: `GOOGLE_API_KEY`
     - Secret: seleccionar `google-api-key`
     - Version: `latest`
     - Reference method: **"Exposed as environment variable"**
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

#### Rotación de la API key (si se compromete)

Si necesitas rotar la key (por ejemplo, si se expuso en un commit):

**Desde Cloud Shell / terminal:**

```bash
# 1. Generar nueva API key en aistudio.google.com/app/apikeys
# 2. Revocar la key anterior en AI Studio
# 3. Agregar nueva versión al secreto:
echo -n "NUEVA_API_KEY" | gcloud secrets versions add google-api-key \
  --data-file=- \
  --project=project-d145b0df-76c9-4324-a6c

# 4. Cloud Run usará la nueva versión automáticamente (usa "latest")
#    Solo necesitas hacer un nuevo deploy o reiniciar las instancias:
gcloud run services update agente-ia-backend \
  --region=us-central1 \
  --project=project-d145b0df-76c9-4324-a6c
```

**Desde la consola GCP:**

1. Ve a **Secret Manager → `google-api-key`**
2. Click **"+ New Version"**
3. Pega la nueva API key → **"Add New Version"**
4. (Opcional) Deshabilita o destruye la versión anterior
5. Ve a **Cloud Run → `agente-ia-backend`** → **"Edit & Deploy New Revision"** → **"Deploy"**

> **⚠️ Sobre la cuota de Vertex AI:** Si el error `429 RESOURCE_EXHAUSTED` persiste en Cloud Run,
> cambiar `USE_VERTEX_AI=false` en las env vars del servicio. Esto usará Google AI Studio (gratis)
> para embeddings en lugar de Vertex AI. Requiere re-ingestar documentos.

---

### 7. Frontend (Next.js → Vercel) — ✅ COMPLETADO

| Campo | Valor |
|-------|-------|
| **Framework** | Next.js (TypeScript) |
| **URL producción** | `https://project-genai.vercel.app/` |
| **Repo** | Mismo repo GitHub, Root Directory: `frontend` |
| **Variable de entorno** | `NEXT_PUBLIC_API_URL` → URL de Cloud Run |

**Configuración en Vercel:**

1. Importar proyecto desde GitHub
2. **Root Directory**: `frontend` (importante, si no da 404)
3. **Environment Variables**: `NEXT_PUBLIC_API_URL` = URL de Cloud Run
4. Deploy automático al hacer push a `main`

**Funcionalidades del frontend:**

- Chat con el agente (sesiones por `session_id`)
- Sugerencias de preguntas predefinidas
- Historial de conversación
- Auto-scroll, Enter para enviar, Shift+Enter para nueva línea
- Soporte dark mode
- Botón de nueva conversación

### 8. URLs de producción

| Servicio | URL |
|----------|-----|
| **Backend (Cloud Run)** | `https://agente-ia-backend-911975904529.us-central1.run.app` |
| **Frontend (Vercel)** | `https://project-genai.vercel.app/` |
| **Health Check** | `https://agente-ia-backend-911975904529.us-central1.run.app/api/health` |
| **Swagger UI** | `https://agente-ia-backend-911975904529.us-central1.run.app/docs` |

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

## Artifact Registry vs Cloud Build Trigger — Diferencias y funcionamiento

Son dos servicios distintos que trabajan en secuencia: uno construye, el otro almacena.

### Analogía

```
Trigger (build-agente-ia-repo)     →     Repositorio (agente-ia-repo)
        "la fábrica"                           "la bodega"

  Toma tu código fuente                  Guarda la imagen ya construida
  Ejecuta el Dockerfile                  Lista para que Cloud Run la use
  Produce una imagen Docker         →    y la descargue cuando desplegue
```

### Artifact Registry — `agente-ia-repo`

**Qué es:** Almacén de imágenes Docker privado dentro del proyecto GCP.

**Qué guarda:**

```text
agente-ia-repo/
└── backend
    ├── sha256:abc123...   ← versión 1 (primer build)
    ├── sha256:def456...   ← versión 2 (segundo build)
    └── latest             ← siempre apunta al más reciente
```

- Cloud Build **escribe** aquí después de construir
- Cloud Run **lee** de aquí cuando despliega
- No ejecuta nada — solo almacena

### Cloud Build Trigger — `build-agente-ia-repo`

**Qué es:** Regla automática que dice "cuando ocurra X evento, ejecuta este proceso de build".

**Flujo al hacer `git push origin main`:**

```text
1. GitHub detecta el push en rama main
2. GitHub notifica a Cloud Build (via webhook)
3. El trigger "build-agente-ia-repo" se activa
4. Cloud Build descarga tu código del repo
5. Lee cloudbuild.yaml → ejecuta docker build con el Dockerfile
6. Publica la imagen resultante en agente-ia-repo
7. Build completado ✅ (visible en Cloud Build → History)
```

No almacena nada — solo orquesta el proceso de construcción.

### Flujo completo en el proyecto

```text
Tu máquina                GCP
──────────                ──────────────────────────────────────────────
                          Cloud Build Trigger
git push       ────────▶  build-agente-ia-repo
origin main               │
                          │  Lee cloudbuild.yaml
                          │  Ejecuta Dockerfile
                          ▼
                          Artifact Registry
                          agente-ia-repo/backend:latest
                          │
                          │  Cloud Run descarga la imagen al deployar
                          ▼
                          Cloud Run — agente-ia-backend
                          https://agent-backend-xxx.run.app
```

### Comparativa

| | Trigger `build-agente-ia-repo` | Repositorio `agente-ia-repo` |
|---|---|---|
| **Tipo** | Cloud Build Trigger | Artifact Registry Repository |
| **Rol** | Orquestador / fábrica | Almacén / bodega |
| **Se activa** | Con `git push` a `main` | Nunca (pasivo, solo recibe) |
| **Qué hace** | Construye la imagen Docker | Guarda la imagen Docker |
| **Quién escribe** | Cloud Build (el trigger) | Cloud Build (resultado del build) |
| **Quién lee** | Nadie | Cloud Run al desplegar |
| **Persiste** | No (el proceso termina) | Sí (guarda todas las versiones) |

> Sin el **trigger** → habría que construir la imagen manualmente con `gcloud builds submit` cada vez.
> Sin el **repositorio** → la imagen no tendría dónde guardarse y Cloud Run no podría descargarla.

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
| API key expuesta en GitHub | Key hardcodeada en archivo versionado (commit) | Usar `<TU_API_KEY>` en docs. Almacenar keys reales en Secret Manager o `.env` (gitignored). Si se expone: rotar inmediatamente, limpiar historial con `git filter-repo`, y force push |
| `Failed to trigger build: if 'build.service_account' is specified...` | Al usar SA personalizada en el trigger, Cloud Build exige configurar dónde guardar logs | Agregar `options: logging: CLOUD_LOGGING_ONLY` en `cloudbuild.yaml` |
| `fatal: pathspec 'project_genai/cloudbuild.yaml' did not match any files` | El repo git tiene raíz en `project_genai/`, no en el directorio padre | Usar rutas relativas a la raíz del repo: `git add cloudbuild.yaml` (sin prefijo `project_genai/`) |
| `Killed` durante ingesta en Cloud Shell | Cloud Shell tiene ~1.7 GB RAM. Cargar todos los PDFs + embeddings en memoria agota la RAM | Procesar PDF por PDF con `gc.collect()`, guardar checkpoints a disco cada 5 PDFs, batch size de 5 |
| `service account info is missing 'email' field` | ADC expirado en Cloud Shell tras reinicio de sesión | Ejecutar `gcloud auth application-default login` antes de la ingesta |
| `429 RESOURCE_EXHAUSTED` en embeddings | Vertex AI quota de `textembedding-gecko` por minuto agotada | Reintentos con backoff exponencial (2, 4, 8, 16, 32s) + pausa de 2s entre lotes |
| `DeprecationWarning: VertexAIEmbeddings` | Clase deprecada en langchain 3.2.0 | Funcional pero migrar a `GoogleGenerativeAIEmbeddings` del paquete `langchain-google-genai` en el futuro |

---

## Git / GitHub — Flujo de trabajo recomendado

### Comandos esenciales

```bash
# Ver estado de cambios
git status

# Ver diferencias (salir con 'q')
git diff

# Agregar archivos al staging
git add .                          # todos los archivos
git add cloudbuild.yaml            # archivo específico

# Hacer commit
git commit -m "descripción del cambio"

# Subir al remoto
git push origin main               # primera vez sin -u
git push -u origin main            # vincula rama local con remota (solo primera vez)
git push                           # siguientes veces (si ya se usó -u)

# Traer cambios del remoto
git pull origin main

# Ver historial
git log --oneline
```

### ¿Qué significa `-u` en `git push`?

El flag `-u` (`--set-upstream`) vincula la rama local con la remota. Solo se necesita la **primera vez** que subes una rama nueva. Después basta con `git push` / `git pull` sin especificar rama.

### Rutas en `git add` — regla importante

Las rutas en `git add` son **relativas a la raíz del repositorio** (donde está la carpeta `.git`), no al directorio de trabajo desde donde ejecutas el comando.

```bash
# Si la raíz del repo es project_genai/:
git add cloudbuild.yaml             # ✅ correcto
git add project_genai/cloudbuild.yaml  # ❌ error si ya estás dentro de project_genai/
```

---

## Buenas prácticas de Service Accounts en producción

### Principio base: mínimo privilegio + una SA por servicio

En producción **no usar una sola SA para todo**. Separar por responsabilidad:

| Service Account | Roles mínimos | Responsabilidad |
|---|---|---|
| `sa-cloudbuild` | `cloudbuild.builds.editor`, `artifactregistry.writer`, `storage.objectViewer`, `logging.logWriter` | Solo construye y sube imágenes |
| `sa-cloudrun` | `run.invoker`, `secretmanager.secretAccessor`, `artifactregistry.reader`, `aiplatform.user` | Solo ejecuta la app y lee secretos |
| `sa-github-actions` | `iam.serviceAccountTokenCreator` | Solo para CI/CD desde GitHub Actions |

### Lo que NO hacer en producción

```text
❌ Una sola SA con roles Owner o Editor
❌ SA con roles que no necesita
❌ Compartir SA entre múltiples servicios críticos
❌ Dejar JSON keys en el código o .env
```

### Autenticación recomendada según entorno

| Entorno | Método | Por qué |
| --- | --- | --- |
| **Desarrollo local** | `gcloud auth application-default login` (ADC) | Sin JSON keys, usa tu cuenta Google |
| **Cloud Run** | Workload Identity (automático) | Sin JSON keys, GCP lo gestiona internamente |
| **GitHub Actions** | Workload Identity Federation | Sin JSON keys, usa tokens OIDC temporales |

> **Regla general:** si una SA es comprometida, el daño debe quedar contenido solo en lo que esa SA puede hacer. Una SA con permisos mínimos limita el radio de impacto.
