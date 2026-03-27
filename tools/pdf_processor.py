"""
tools/pdf_processor.py — Procesamiento y fragmentación de PDFs

Extrae texto de archivos PDF, lo limpia y lo divide en fragmentos (chunks)
optimizados para búsqueda semántica RAG.

Pipeline:
  1. Extraer texto por página con pypdf
  2. Limpiar texto (espacios, caracteres especiales)
  3. Dividir en fragmentos con overlap para mantener contexto
  4. Generar keywords automáticas por fragmento

En producción: usar Cloud Document AI para OCR de PDFs escaneados.
"""

import re
from pathlib import Path

# Configuración de fragmentación
CHUNK_SIZE = 500       # Caracteres por fragmento
CHUNK_OVERLAP = 100    # Solapamiento entre fragmentos para mantener contexto
MIN_CHUNK_LENGTH = 50  # Ignorar fragmentos muy cortos


def extraer_texto_pdf(ruta_pdf: Path) -> list[dict]:
    """
    Extrae texto de un PDF página por página.

    Args:
        ruta_pdf: Ruta al archivo PDF

    Returns:
        Lista de dicts con {texto, pagina, fuente}
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "Se requiere pypdf para procesar PDFs.\n"
            "Instalar con: pip install pypdf"
        )

    reader = PdfReader(str(ruta_pdf))
    nombre_archivo = ruta_pdf.name
    paginas = []

    for i, page in enumerate(reader.pages, start=1):
        texto = page.extract_text()
        if texto and texto.strip():
            paginas.append({
                "texto": texto.strip(),
                "pagina": i,
                "fuente": nombre_archivo
            })

    return paginas


def limpiar_texto(texto: str) -> str:
    """
    Limpia texto extraído de PDF: normaliza espacios, elimina caracteres
    de control y artefactos de extracción.
    """
    # Eliminar caracteres de control excepto saltos de línea
    texto = re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f]', '', texto)
    # Normalizar saltos de línea múltiples
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    # Normalizar espacios múltiples
    texto = re.sub(r'[ \t]{2,}', ' ', texto)
    # Limpiar líneas que solo tienen espacios
    texto = re.sub(r'\n\s+\n', '\n\n', texto)
    return texto.strip()


def _generar_keywords(texto: str) -> list[str]:
    """
    Genera keywords relevantes de un fragmento de texto.
    Extrae palabras significativas (> 3 chars, no stopwords).
    """
    # Stopwords en español comunes
    stopwords = {
        "para", "como", "este", "esta", "esto", "esos", "esas", "unos", "unas",
        "ante", "bajo", "cabe", "contra", "desde", "entre", "hacia", "hasta",
        "según", "sobre", "tras", "cada", "todo", "toda", "todos", "todas",
        "otro", "otra", "otros", "otras", "mismo", "misma", "mismos", "mismas",
        "debe", "deben", "puede", "pueden", "será", "serán", "tiene", "tienen",
        "sido", "sido", "estar", "están", "haber", "habido", "siendo", "sean",
        "también", "además", "cuando", "donde", "quien", "cual", "cuyo",
        "porque", "aunque", "sino", "pero", "más", "menos", "algo", "nada",
        "mucho", "poco", "bien", "aquí", "allí", "ahora", "antes", "después",
        "siempre", "nunca", "solo", "solo", "ya", "aún", "con", "sin",
        "por", "que", "del", "los", "las", "una", "uno", "sus", "les",
    }

    # Extraer palabras, convertir a minúsculas
    palabras = re.findall(r'\b[a-záéíóúñü]+\b', texto.lower())

    # Filtrar stopwords y palabras cortas, mantener únicas
    keywords = list(set(
        p for p in palabras
        if len(p) > 3 and p not in stopwords
    ))

    return sorted(keywords)[:20]  # Máximo 20 keywords por fragmento


def fragmentar_texto(texto: str, chunk_size: int = CHUNK_SIZE,
                     overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Divide texto en fragmentos con solapamiento.
    Intenta cortar en límites de oración para mantener coherencia.

    Args:
        texto: Texto completo a fragmentar
        chunk_size: Tamaño máximo de cada fragmento en caracteres
        overlap: Caracteres de solapamiento entre fragmentos

    Returns:
        Lista de fragmentos de texto
    """
    if len(texto) <= chunk_size:
        return [texto] if len(texto) >= MIN_CHUNK_LENGTH else []

    fragmentos = []
    inicio = 0

    while inicio < len(texto):
        fin = inicio + chunk_size

        # Si no estamos al final, buscar un punto de corte natural
        if fin < len(texto):
            # Buscar el último punto, salto de línea o punto y coma antes del límite
            corte = max(
                texto.rfind('. ', inicio, fin),
                texto.rfind('\n', inicio, fin),
                texto.rfind('; ', inicio, fin),
            )
            if corte > inicio + MIN_CHUNK_LENGTH:
                fin = corte + 1  # Incluir el punto/salto

        fragmento = texto[inicio:fin].strip()
        if len(fragmento) >= MIN_CHUNK_LENGTH:
            fragmentos.append(fragmento)

        # Avanzar con overlap
        inicio = fin - overlap if fin < len(texto) else len(texto)

    return fragmentos


def procesar_pdf(ruta_pdf: Path) -> list[dict]:
    """
    Pipeline completo: extrae texto de un PDF, lo limpia, fragmenta
    y genera keywords para búsqueda.

    Args:
        ruta_pdf: Ruta al archivo PDF

    Returns:
        Lista de fragmentos listos para la base de conocimiento RAG.
        Cada fragmento: {texto, fuente, pagina, keywords, categoria}
    """
    # Determinar categoría por nombre de archivo
    nombre_lower = ruta_pdf.name.lower()
    if "politica" in nombre_lower or "política" in nombre_lower or "codigo" in nombre_lower:
        categoria = "POLITICAS"
    elif "procedimiento" in nombre_lower:
        categoria = "PROCEDIMIENTOS"
    elif "reglamento" in nombre_lower:
        categoria = "REGLAMENTOS"
    else:
        categoria = "OTROS"

    # Extraer texto por página
    paginas = extraer_texto_pdf(ruta_pdf)
    fragmentos_resultado = []

    for pagina_info in paginas:
        texto_limpio = limpiar_texto(pagina_info["texto"])
        chunks = fragmentar_texto(texto_limpio)

        for chunk in chunks:
            keywords = _generar_keywords(chunk)
            fragmentos_resultado.append({
                "texto": chunk,
                "fuente": pagina_info["fuente"],
                "pagina": pagina_info["pagina"],
                "keywords": keywords,
                "categoria": categoria,
            })

    return fragmentos_resultado


def procesar_directorio(directorio: Path) -> list[dict]:
    """
    Procesa todos los PDFs de un directorio recursivamente.

    Args:
        directorio: Ruta al directorio con PDFs

    Returns:
        Lista unificada de fragmentos de todos los PDFs
    """
    if not directorio.exists():
        print(f"⚠️  Directorio no encontrado: {directorio}")
        return []

    pdfs = sorted(directorio.rglob("*.pdf"))
    if not pdfs:
        print(f"⚠️  No se encontraron PDFs en: {directorio}")
        return []

    print(f"📄 Procesando {len(pdfs)} PDFs desde {directorio}...")

    todos_fragmentos = []
    for pdf in pdfs:
        try:
            fragmentos = procesar_pdf(pdf)
            todos_fragmentos.extend(fragmentos)
            print(f"  ✅ {pdf.name}: {len(fragmentos)} fragmentos")
        except Exception as e:
            print(f"  ❌ Error procesando {pdf.name}: {e}")

    print(f"\n📊 Total: {len(todos_fragmentos)} fragmentos de {len(pdfs)} PDFs")
    return todos_fragmentos


# ========================================
# Ejecución directa: procesar PDFs locales
# ========================================
if __name__ == "__main__":
    from drive_loader import DEFAULT_DOCS_DIR

    print("=" * 60)
    print("📄 Procesador de PDFs para RAG")
    print("=" * 60)

    fragmentos = procesar_directorio(DEFAULT_DOCS_DIR)

    if fragmentos:
        print(f"\n📋 Ejemplo de fragmento:")
        ejemplo = fragmentos[0]
        print(f"  Fuente: {ejemplo['fuente']}, pág. {ejemplo['pagina']}")
        print(f"  Categoría: {ejemplo['categoria']}")
        print(f"  Keywords: {ejemplo['keywords'][:10]}")
        print(f"  Texto: {ejemplo['texto'][:200]}...")
