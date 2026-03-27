# /credentials — Credenciales de servicio (NO subir a git)

Este directorio almacena las credenciales de Google Cloud Platform.

## Archivo esperado

```
credentials/
└── service_account.json   ← Archivo JSON de la Service Account de GCP
```

## Cómo obtener el archivo

1. Ir a [Google Cloud Console](https://console.cloud.google.com/)
2. Navegá a **IAM & Admin → Service Accounts**
3. Seleccioná tu Service Account (o creá una nueva)
4. Pestaña **Keys → Add Key → Create new key → JSON**
5. Descargá el archivo y renombralo a `service_account.json`
6. Copialo a esta carpeta: `credentials/service_account.json`

## Permisos necesarios en la Service Account

| Permiso | Motivo |
|---------|--------|
| `drive.readonly` | Leer archivos de la carpeta compartida en Google Drive |

## Compartir la carpeta de Drive

La carpeta de Google Drive con los PDFs debe estar **compartida** con el email
de la Service Account (aparece en el JSON como `client_email`), por ejemplo:

```
mi-service-account@mi-proyecto.iam.gserviceaccount.com
```

Compartir con permiso de **Lector (Viewer)**.

## Seguridad

- Este directorio está en `.gitignore` — los archivos `.json` NUNCA se suben al repositorio
- No compartas el archivo JSON por canales inseguros
- Rotá las claves periódicamente desde la consola de GCP
