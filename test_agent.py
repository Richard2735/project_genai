"""
test_agent.py — Pruebas unitarias para verificar cada Tool

Ejecuta pruebas para verificar que cada herramienta funciona correctamente
sin necesidad de inicializar el agente completo.

Uso:
  python test_agent.py
"""

import sys
import io
import tempfile
from pathlib import Path

# Forzar UTF-8 en Windows para soportar emojis en consola
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from tools.data_prep import data_prep_tool
from tools.rag_search import rag_search_tool
from tools.dlp_anonymizer import dlp_anonymizer_tool


def test_data_prep_tool():
    """Prueba Tool 1: data_prep_tool"""
    print("\n" + "="*70)
    print("TEST 1: data_prep_tool (Preparacion de datos)")
    print("="*70)

    raw_html = """
    <div class='content'>
        <h1>Resumen Ejecutivo</h1>
        <p>La empresa ha registrado un crecimiento del 15% en Q4 2024.
        Se han invertido $5,000,000 en infraestructura de cloud.</p>
        <span>Contacto: info@empresa.com</span>
    </div>
    """

    print(f"\n  Input (HTML con ruido):\n{raw_html[:100]}...\n")

    result = data_prep_tool.invoke({"raw_text": raw_html})
    print(f"  Output (JSONL limpio):\n{result}\n")

    assert "messages" in result, "El output debe contener 'messages'"
    assert "user" in result, "El output debe contener rol 'user'"
    assert "assistant" in result, "El output debe contener rol 'assistant'"
    print("[PASS] Test 1: Texto limpio y estructurado en JSONL\n")


def test_rag_search_tool():
    """Prueba Tool 2: rag_search_tool (FAISS semantico o mock fallback)"""
    print("="*70)
    print("TEST 2: rag_search_tool (Busqueda RAG)")
    print("="*70)

    # Detectar si FAISS esta disponible
    from config.settings import FAISS_INDEX_DIR
    faiss_disponible = (FAISS_INDEX_DIR / "index.faiss").exists()

    if faiss_disponible:
        print("\n  Modo: BUSQUEDA SEMANTICA (FAISS + Gemini Embeddings)")
    else:
        print("\n  Modo: FALLBACK KEYWORDS (sin indice FAISS)")

    # Queries de prueba — validamos estructura y pertinencia del resultado
    # Estas queries funcionan tanto con FAISS (semantico) como con mock (keywords)
    queries = [
        ("politica de seguridad de la informacion",   "seguridad"),
        ("teletrabajo trabajo remoto",                "teletrabajo"),
        ("procedimiento de calidad",                  "calidad"),
        ("reglamento interno",                        "reglamento"),
    ]

    for query, tema in queries:
        print(f"\n  Query: '{query}'")
        result = rag_search_tool.invoke({"query": query})

        # Mostrar primeros 400 chars del resultado
        preview = result[:400].replace("\n", "\n    ")
        print(f"    {preview}...")

        # Validaciones estructurales
        assert len(result) > 0, f"Busqueda vacia para: {query}"
        assert "Resultado" in result, f"Sin resultados formateados para: {query}"
        assert "Doc:" in result, f"Sin referencia de documento para: {query}"

        # Validar pertinencia: el tema debe aparecer en el resultado
        result_lower = result.lower()
        assert tema in result_lower, (
            f"Resultado no es pertinente: se esperaba '{tema}' en la respuesta "
            f"para la query '{query}'"
        )

    # Caso sin resultados relevantes (solo funciona bien en modo mock)
    if not faiss_disponible:
        print("\n  Query sin resultados: 'xyzzy foobar quux'")
        result_vacio = rag_search_tool.invoke({"query": "xyzzy foobar quux"})
        assert "No se encontraron" in result_vacio, "Debe indicar cuando no hay resultados"
        print(f"    {result_vacio[:200]}")

    print(f"\n[PASS] Test 2: Busqueda RAG funcionando ({'FAISS' if faiss_disponible else 'mock'})\n")


def test_dlp_anonymizer_tool():
    """Prueba Tool 3: dlp_anonymizer_tool"""
    print("="*70)
    print("TEST 3: dlp_anonymizer_tool (Anonimizacion PII)")
    print("="*70)

    text_with_pii = """
    Estimado cliente,

    Su solicitud de credito ha sido procesada.
    Datos personales:
    - Nombre: Juan Perez Garcia
    - DNI: 12345678
    - Telefono: +51 987654321
    - Correo: juan.perez@empresa.com.pe
    - Tarjeta: 4532 1234 5678 9010
    - RUC: 20123456789

    Por favor confirme su informacion para continuar.
    Saludos,
    Banco Seguro
    """

    print(f"\n  Input (con PII sensible):\n{text_with_pii}\n")

    result = dlp_anonymizer_tool.invoke({"text": text_with_pii})
    print(f"  Output (anonimizado):\n{result}\n")

    assert "[EMAIL]" in result, "Los emails deben ser anonimizados"
    assert "[DNI]" in result, "Los DNI deben ser anonimizados"
    assert "juan.perez@" not in result, "El email original no debe aparecer"

    print("[PASS] Test 3: PII detectada y anonimizada correctamente\n")


def test_pdf_processor():
    """Prueba del procesador de PDFs"""
    print("="*70)
    print("TEST 4: pdf_processor (Procesamiento de PDFs)")
    print("="*70)

    from tools.pdf_processor import (
        limpiar_texto,
        fragmentar_texto,
        _generar_keywords,
    )

    # Test limpiar_texto
    texto_sucio = "  Hola   mundo  \n\n\n\n  esto   es   \x00  una prueba  "
    texto_limpio = limpiar_texto(texto_sucio)
    assert "\x00" not in texto_limpio, "No debe contener caracteres de control"
    assert "   " not in texto_limpio, "No debe tener espacios triples"
    print(f"\n  [OK] limpiar_texto funciona")

    # Test fragmentar_texto
    texto_largo = "Esta es una oracion. " * 50
    fragmentos = fragmentar_texto(texto_largo, chunk_size=200, overlap=50)
    assert len(fragmentos) > 1, "Debe generar multiples fragmentos"
    print(f"  [OK] fragmentar_texto: {len(texto_largo)} chars -> {len(fragmentos)} fragmentos")

    # Test generar_keywords
    texto_test = "La politica de seguridad de la informacion establece requisitos de acceso"
    keywords = _generar_keywords(texto_test)
    assert len(keywords) > 0, "Debe generar al menos 1 keyword"
    assert all(len(kw) > 3 for kw in keywords), "Keywords deben tener > 3 caracteres"
    print(f"  [OK] generar_keywords: {len(keywords)} keywords -> {keywords[:5]}...")

    print("\n[PASS] Test 4: Procesador de PDFs funcionando\n")


def test_drive_loader():
    """Prueba del cargador de Google Drive (funcionalidad local)"""
    print("="*70)
    print("TEST 5: drive_loader (Carga desde Google Drive)")
    print("="*70)

    from tools.drive_loader import (
        _clasificar_documento,
        listar_pdfs_locales,
        obtener_estadisticas,
        DEFAULT_DOCS_DIR,
    )

    # Test clasificacion de documentos por nombre
    casos_clasificacion = [
        ("Politica- Seguridad de la informacion.pdf", "POLITICAS"),
        ("Politica-Teletrabajo.pdf", "POLITICAS"),
        ("Codigo de Etica y conducta.pdf", "POLITICAS"),
        ("Procedimiento control documentario.pdf", "PROCEDIMIENTOS"),
        ("Reglamento Interno de Trabajo.pdf", "REGLAMENTOS"),
        ("Documento_General.pdf", "OTROS"),
    ]

    for nombre, categoria_esperada in casos_clasificacion:
        categoria = _clasificar_documento(nombre)
        assert categoria == categoria_esperada, (
            f"'{nombre}' deberia ser '{categoria_esperada}', no '{categoria}'"
        )
        print(f"  [OK] '{nombre}' -> {categoria}")

    # Test listar PDFs locales
    pdfs = listar_pdfs_locales()
    print(f"\n  PDFs locales encontrados: {len(pdfs)}")

    # Test estadisticas
    stats = obtener_estadisticas()
    assert "total" in stats, "Estadisticas deben incluir 'total'"
    assert "por_categoria" in stats, "Estadisticas deben incluir 'por_categoria'"
    print(f"  Estadisticas: {stats}")

    print("\n[PASS] Test 5: Drive loader funcionando\n")


def test_faiss_index():
    """Prueba del indice FAISS (si existe)"""
    print("="*70)
    print("TEST 6: Indice FAISS (Vector Store)")
    print("="*70)

    from config.settings import FAISS_INDEX_DIR

    faiss_file = FAISS_INDEX_DIR / "index.faiss"
    pkl_file = FAISS_INDEX_DIR / "index.pkl"

    if not faiss_file.exists():
        print("\n  Indice FAISS no encontrado en vectorstore/")
        print("  Para crearlo ejecuta: python scripts/ingestar_documentos.py")
        print("\n[SKIP] Test 6: Sin indice FAISS\n")
        return

    # Verificar que ambos archivos existen
    assert faiss_file.exists(), "Falta index.faiss"
    assert pkl_file.exists(), "Falta index.pkl"
    print(f"\n  [OK] index.faiss encontrado ({faiss_file.stat().st_size / 1024:.1f} KB)")
    print(f"  [OK] index.pkl encontrado ({pkl_file.stat().st_size / 1024:.1f} KB)")

    # Cargar y verificar el indice
    from tools.rag_search import recargar_vectorstore
    vectorstore = recargar_vectorstore()
    assert vectorstore is not None, "No se pudo cargar el indice FAISS"

    num_vectores = vectorstore.index.ntotal
    print(f"  [OK] Indice cargado: {num_vectores} vectores")
    assert num_vectores > 0, "El indice esta vacio"

    # Prueba de busqueda semantica
    query = "politica de seguridad"
    resultados = vectorstore.similarity_search_with_score(query, k=2)
    assert len(resultados) > 0, "La busqueda no retorno resultados"

    for i, (doc, score) in enumerate(resultados, 1):
        relevancia = 1 / (1 + score) * 100
        print(f"  [OK] Resultado {i}: {doc.metadata['fuente']} (relevancia: {relevancia:.1f}%)")

    print(f"\n[PASS] Test 6: Indice FAISS funcionando ({num_vectores} vectores)\n")


def run_all_tests():
    """Ejecuta todas las pruebas"""
    print("\n" + "#"*70)
    print("# SUITE DE PRUEBAS - Proyecto Integrador Modulo II")
    print("#"*70)

    try:
        test_data_prep_tool()
        test_rag_search_tool()
        test_dlp_anonymizer_tool()
        test_pdf_processor()
        test_drive_loader()
        test_faiss_index()

        print("\n" + "#"*70)
        print("# [OK] TODAS LAS PRUEBAS PASARON EXITOSAMENTE")
        print("#"*70 + "\n")

    except AssertionError as e:
        print(f"\n[FAIL] Error en prueba: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
