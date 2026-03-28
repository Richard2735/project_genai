"""
utils/gcs_helpers.py — Utilidades para interactuar con Google Cloud Storage.

Este modulo centraliza todas las operaciones con GCS que necesitan
tanto el pipeline de ingesta (Cloud Run Job) como el backend (Cloud Run Service).

Funciones:
  - descargar_pdfs_desde_gcs(): Descarga PDFs del bucket a directorio local
  - subir_vectorstore_a_gcs(): Sube index.faiss + index.pkl al bucket
  - descargar_vectorstore_desde_gcs(): Descarga el indice FAISS desde GCS

¿Por que un bucket GCS?
-----------------------
En una arquitectura de produccion como Data Engineer, los datos de entrada
(PDFs) y los artefactos generados (indice FAISS) deben vivir en almacenamiento
persistente y compartido, no en el filesystem local de un contenedor efimero.

GCS actua como la "fuente de verdad" (source of truth):
  - Los PDFs se suben una vez al bucket y quedan disponibles
  - El Cloud Run Job lee de ahi, genera el indice, y lo sube de vuelta
  - El Cloud Run Service descarga el indice al arrancar

Esto sigue el principio de "stateless containers" de Cloud Run:
los contenedores no guardan estado, todo el estado esta en GCS.
"""

from pathlib import Path
from google.cloud import storage


def descargar_pdfs_desde_gcs(bucket_name: str, prefix: str, destino_local: Path) -> int:
    """
    Descarga todos los PDFs de un bucket GCS a un directorio local.

    Preserva la estructura de subdirectorios (POLITICAS/, PROCEDIMIENTOS/, etc.)
    para que el pdf_processor pueda determinar la categoria de cada documento.

    ¿Como funciona internamente?
    1. Crea un cliente de GCS (usa ADC o Workload Identity automaticamente)
    2. Lista todos los blobs bajo el prefix que terminan en .pdf
    3. Para cada blob, calcula la ruta relativa y descarga al destino local

    Args:
        bucket_name: Nombre del bucket GCS (sin gs://)
        prefix: Prefijo dentro del bucket (ej: "pdfs/")
        destino_local: Directorio local donde guardar los PDFs

    Returns:
        Numero de PDFs descargados
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix=prefix))

    contador = 0
    for blob in blobs:
        # Solo archivos PDF (ignorar "directorios" vacios en GCS)
        if not blob.name.lower().endswith(".pdf"):
            continue

        # Calcular ruta relativa: quitar el prefix para preservar subcarpetas
        # ej: "pdfs/POLITICAS/Codigo de Etica.pdf" → "POLITICAS/Codigo de Etica.pdf"
        ruta_relativa = blob.name[len(prefix):]
        ruta_local = destino_local / ruta_relativa

        # Crear subdirectorios si no existen
        ruta_local.parent.mkdir(parents=True, exist_ok=True)

        # Descargar
        blob.download_to_filename(str(ruta_local))
        contador += 1

    print(f"  Descargados {contador} PDFs desde gs://{bucket_name}/{prefix}")
    return contador


def subir_vectorstore_a_gcs(bucket_name: str, prefix: str, directorio_local: Path):
    """
    Sube los archivos del indice FAISS (index.faiss + index.pkl) a GCS.

    ¿Por que subir el indice a GCS?
    El Cloud Run Job genera el indice en su filesystem temporal (/tmp).
    Cuando el Job termina, ese filesystem se destruye. Subir a GCS
    persiste el indice para que el Cloud Run Service lo descargue.

    Args:
        bucket_name: Nombre del bucket GCS
        prefix: Prefijo dentro del bucket (ej: "vectorstore/")
        directorio_local: Directorio local con index.faiss e index.pkl
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    archivos = ["index.faiss", "index.pkl"]
    for archivo in archivos:
        ruta_local = directorio_local / archivo
        if not ruta_local.exists():
            print(f"  WARN: No se encontro {ruta_local}")
            continue

        blob_name = f"{prefix}{archivo}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(ruta_local))

        size_mb = ruta_local.stat().st_size / (1024 * 1024)
        print(f"  Subido: gs://{bucket_name}/{blob_name} ({size_mb:.2f} MB)")


def descargar_vectorstore_desde_gcs(bucket_name: str, prefix: str, destino_local: Path) -> bool:
    """
    Descarga el indice FAISS (index.faiss + index.pkl) desde GCS.

    Esta funcion es llamada por el backend (Cloud Run Service) al arrancar.
    Si el indice no existe en GCS (primera vez), retorna False y el backend
    usa el fallback de busqueda por keywords.

    Args:
        bucket_name: Nombre del bucket GCS
        prefix: Prefijo dentro del bucket (ej: "vectorstore/")
        destino_local: Directorio local donde guardar los archivos

    Returns:
        True si ambos archivos se descargaron exitosamente, False si no existen
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    destino_local.mkdir(parents=True, exist_ok=True)

    archivos = ["index.faiss", "index.pkl"]
    descargados = 0

    for archivo in archivos:
        blob_name = f"{prefix}{archivo}"
        blob = bucket.blob(blob_name)

        if not blob.exists():
            print(f"  No existe: gs://{bucket_name}/{blob_name}")
            return False

        ruta_local = destino_local / archivo
        blob.download_to_filename(str(ruta_local))

        size_mb = ruta_local.stat().st_size / (1024 * 1024)
        print(f"  Descargado: gs://{bucket_name}/{blob_name} ({size_mb:.2f} MB)")
        descargados += 1

    return descargados == len(archivos)
