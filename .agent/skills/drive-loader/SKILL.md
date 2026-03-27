---
name: drive-loader
description: |
  Workflow para descargar PDFs desde Google Drive usando Service Account
  o ADC. Clasifica documentos automáticamente en POLITICAS, PROCEDIMIENTOS,
  REGLAMENTOS. Usar cuando se trabaje con Drive API, credenciales de SA,
  o carga de documentos corporativos.
---

## Use this skill when

- Configurando acceso a Google Drive desde Python
- Descargando PDFs corporativos desde carpetas compartidas
- Autenticando con Service Account o ADC (Application Default Credentials)
- Clasificando documentos por tipo (políticas, procedimientos, reglamentos)

## Do not use this skill when

- Procesando el contenido de los PDFs (usar `rag-search` en su lugar)
- Trabajando con APIs que no son Google Drive

## Instructions

### Autenticación con Service Account

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
creds = service_account.Credentials.from_service_account_file(
    "credentials/service_account.json", scopes=SCOPES
)
service = build("drive", "v3", credentials=creds)
```

### Autenticación con ADC (desarrollo local)

```python
import google.auth
creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
service = build("drive", "v3", credentials=creds)
```

### Requisitos previos

1. Habilitar **Google Drive API** en el proyecto GCP
2. Crear Service Account y descargar JSON (o usar `gcloud auth application-default login`)
3. Compartir la carpeta de Drive con el email de la SA (Viewer)
4. Configurar variables en `.env`: `DRIVE_FOLDER_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`

### Clasificación automática

Los PDFs se clasifican por nombre de archivo:
- Contiene "política/politica/código/codigo" → `POLITICAS/`
- Contiene "procedimiento" → `PROCEDIMIENTOS/`
- Contiene "reglamento" → `REGLAMENTOS/`
- Otros → `OTROS/`

## Safety

- Nunca commitear `credentials/service_account.json` — debe estar en `.gitignore`
- Usar permisos de solo lectura (`drive.readonly`) a menos que se necesite escribir
- Validar que los archivos descargados sean PDFs válidos antes de procesarlos
