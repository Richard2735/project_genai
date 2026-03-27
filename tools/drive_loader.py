"""
tools/drive_loader.py — Carga de archivos PDF desde Google Drive

Descarga archivos PDF desde una carpeta de Google Drive usando
una Service Account de GCP. Requiere:
  1. Archivo credentials/service_account.json
  2. Carpeta de Drive compartida con el email de la Service Account
  3. DRIVE_FOLDER_ID configurado en .env

Uso:
  python -m tools.drive_loader
"""

import io
from pathlib import Path

from config.settings import (
    DRIVE_FOLDER_ID,
    DRIVE_SCOPES,
    SERVICE_ACCOUNT_FILE,
    DOCS_DIR,
)

# Directorio local donde se guardan los PDFs descargados
DEFAULT_DOCS_DIR = DOCS_DIR

# Categorías de documentos reconocidas
CATEGORIAS = {
    "politica": "POLITICAS",
    "política": "POLITICAS",
    "codigo": "POLITICAS",
    "código": "POLITICAS",
    "procedimiento": "PROCEDIMIENTOS",
    "reglamento": "REGLAMENTOS",
}


def _clasificar_documento(nombre_archivo: str) -> str:
    """
    Clasifica un PDF en su categoría según el nombre del archivo.
    Retorna la subcarpeta correspondiente (POLITICAS, PROCEDIMIENTOS, REGLAMENTOS).
    """
    nombre_lower = nombre_archivo.lower()
    for keyword, categoria in CATEGORIAS.items():
        if keyword in nombre_lower:
            return categoria
    return "OTROS"


def _autenticar_drive():
    """
    Autentica con Google Drive usando Service Account.
    Retorna un objeto service de la API de Drive v3.
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if not SERVICE_ACCOUNT_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales:\n"
            f"  {SERVICE_ACCOUNT_FILE}\n\n"
            f"Pasos para configurarlo:\n"
            f"  1. Descarga el JSON de tu Service Account desde Google Cloud Console\n"
            f"  2. Renómbralo a 'service_account.json'\n"
            f"  3. Cópialo a: credentials/service_account.json"
        )

    credentials = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE),
        scopes=DRIVE_SCOPES
    )

    service = build("drive", "v3", credentials=credentials)
    return service


def _listar_archivos_recursivo(service, folder_id: str) -> list[dict]:
    """
    Lista todos los PDFs dentro de una carpeta de Drive,
    incluyendo subcarpetas (POLITICAS, PROCEDIMIENTOS, REGLAMENTOS).
    """
    archivos_pdf = []

    # Listar contenido de la carpeta
    query = f"'{folder_id}' in parents and trashed=false"
    resultados = service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
        pageSize=200
    ).execute()

    items = resultados.get("files", [])

    for item in items:
        if item["mimeType"] == "application/pdf":
            archivos_pdf.append(item)
        elif item["mimeType"] == "application/vnd.google-apps.folder":
            # Recursión en subcarpetas
            sub_archivos = _listar_archivos_recursivo(service, item["id"])
            archivos_pdf.extend(sub_archivos)

    return archivos_pdf


def descargar_desde_drive(folder_id: str = None, destino: Path = None) -> list[Path]:
    """
    Descarga todos los PDFs de una carpeta de Google Drive
    autenticándose con Service Account.

    Args:
        folder_id: ID de la carpeta de Google Drive.
                   Si no se proporciona, usa DRIVE_FOLDER_ID de .env
        destino: Directorio local de destino. Por defecto: docs/corporativos/

    Returns:
        Lista de rutas a los archivos PDF descargados
    """
    from googleapiclient.http import MediaIoBaseDownload

    # Configurar folder_id y destino
    folder_id = folder_id or DRIVE_FOLDER_ID
    if not folder_id:
        raise ValueError(
            "No se proporcionó folder_id ni se encontró DRIVE_FOLDER_ID en .env.\n"
            "Configura DRIVE_FOLDER_ID=<id_carpeta_drive> en tu archivo .env"
        )

    destino = destino or DEFAULT_DOCS_DIR
    destino.mkdir(parents=True, exist_ok=True)

    # Autenticar con Service Account
    print("🔐 Autenticando con Service Account...")
    service = _autenticar_drive()

    # Listar archivos PDF (incluye subcarpetas)
    print(f"📂 Buscando PDFs en la carpeta de Drive: {folder_id}")
    archivos = _listar_archivos_recursivo(service, folder_id)

    if not archivos:
        print(f"⚠️  No se encontraron PDFs en la carpeta de Drive: {folder_id}")
        return []

    print(f"📄 Encontrados {len(archivos)} PDFs en Google Drive\n")

    # Descargar cada archivo
    rutas_descargadas = []
    for archivo in archivos:
        nombre = archivo["name"]
        file_id = archivo["id"]

        # Clasificar y crear subcarpeta
        categoria = _clasificar_documento(nombre)
        carpeta_destino = destino / categoria
        carpeta_destino.mkdir(parents=True, exist_ok=True)

        ruta_local = carpeta_destino / nombre

        # Saltar si ya existe (cache local)
        if ruta_local.exists():
            print(f"  ✅ Ya existe: {nombre} [{categoria}]")
            rutas_descargadas.append(ruta_local)
            continue

        # Descargar archivo
        print(f"  ⬇️  Descargando: {nombre}...")
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        # Guardar en disco
        with open(ruta_local, "wb") as f:
            f.write(buffer.getvalue())

        rutas_descargadas.append(ruta_local)
        print(f"  ✅ Guardado: {nombre} → {categoria}/")

    print(f"\n📁 Total descargados: {len(rutas_descargadas)} archivos en {destino}")
    return rutas_descargadas


def listar_pdfs_locales(directorio: Path = None) -> list[Path]:
    """
    Lista todos los archivos PDF disponibles en el directorio local.
    Busca recursivamente en subdirectorios (POLITICAS, PROCEDIMIENTOS, REGLAMENTOS).
    """
    directorio = directorio or DEFAULT_DOCS_DIR
    if not directorio.exists():
        return []
    return sorted(directorio.rglob("*.pdf"))


def obtener_estadisticas(directorio: Path = None) -> dict:
    """
    Retorna estadísticas de los documentos cargados.
    """
    directorio = directorio or DEFAULT_DOCS_DIR
    pdfs = listar_pdfs_locales(directorio)

    stats = {"total": len(pdfs), "por_categoria": {}}
    for pdf in pdfs:
        categoria = pdf.parent.name
        stats["por_categoria"][categoria] = stats["por_categoria"].get(categoria, 0) + 1

    return stats


# ========================================
# Ejecución directa: descarga PDFs de Drive
# ========================================
if __name__ == "__main__":
    print("=" * 60)
    print("📥 Descargador de PDFs desde Google Drive")
    print("    (Autenticación: Service Account)")
    print("=" * 60)

    from config.settings import imprimir_estado
    imprimir_estado()

    try:
        rutas = descargar_desde_drive()
        stats = obtener_estadisticas()
        print(f"\n📊 Estadísticas: {stats}")
    except FileNotFoundError as e:
        print(f"\n❌ Credenciales no encontradas:\n{e}")
    except (ValueError, ImportError) as e:
        print(f"\n❌ {e}")

        locales = listar_pdfs_locales()
        if locales:
            print(f"\n📁 Archivos locales disponibles: {len(locales)}")
            for pdf in locales:
                print(f"  📄 {pdf}")
