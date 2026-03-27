"""
scripts/descargar_pdfs.py — Script para descargar PDFs de Google Drive

Uso:
  cd s13/
  python scripts/descargar_pdfs.py

Prerequisitos:
  1. Archivo credentials/service_account.json configurado
  2. DRIVE_FOLDER_ID en .env
  3. Carpeta de Drive compartida con el email de la Service Account
"""

import sys
from pathlib import Path

# Agregar directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import imprimir_estado, validar_configuracion
from tools.drive_loader import descargar_desde_drive, obtener_estadisticas


def main():
    print("\n" + "=" * 60)
    print("📥 Descarga de documentos corporativos desde Google Drive")
    print("=" * 60)

    # Validar configuración
    estado = imprimir_estado()

    if not estado["service_account"]:
        print("❌ No se encontró credentials/service_account.json")
        print("   Consulta credentials/README.md para instrucciones")
        sys.exit(1)

    if not estado["drive_folder_id"]:
        print("❌ No se encontró DRIVE_FOLDER_ID en .env")
        sys.exit(1)

    # Descargar
    try:
        rutas = descargar_desde_drive()
        stats = obtener_estadisticas()

        print("\n" + "=" * 60)
        print("📊 Resumen de descarga")
        print("=" * 60)
        print(f"  Total PDFs: {stats['total']}")
        for cat, count in stats["por_categoria"].items():
            print(f"  📁 {cat}: {count} archivos")

        if rutas:
            print("\n✅ Descarga completada exitosamente")
            print("   Los PDFs están en: docs/corporativos/")
            print("   Ejecuta 'python test_agent.py' para verificar la integración RAG")
        else:
            print("\n⚠️  No se descargaron archivos nuevos")

    except Exception as e:
        print(f"\n❌ Error durante la descarga: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
