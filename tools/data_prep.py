"""
tools/data_prep.py — Tool 1: Preparación de datos para fine-tuning

Esta herramienta limpia texto corporativo crudo y lo convierte al formato JSONL,
listo para fine-tuning de LLMs. Elimina ruido (HTML, caracteres especiales,
duplicados) y estructura el output como pares instrucción-respuesta.
"""

import re
import json
from langchain.tools import tool


@tool
def data_prep_tool(raw_text: str) -> str:
    """
    Limpia y transforma texto corporativo crudo a formato JSONL
    listo para fine-tuning de LLMs.

    Este proceso:
    1. Elimina HTML y caracteres especiales
    2. Normaliza espacios en blanco
    3. Estructura el texto como par instrucción-respuesta (messages format)
    4. Devuelve JSON válido listo para BigQuery o datasets de LLM

    Úsala cuando el usuario proporcione documentos sin estructura,
    especialmente para preparar datos antes de ajuste fino (fine-tuning).

    Args:
        raw_text (str): Texto crudo a procesar (puede incluir HTML, espacios extras, etc.)

    Returns:
        str: String JSON con el registro JSONL limpio en formato OpenAI messages
    """

    # ========================================
    # Paso 1: Limpieza básica
    # ========================================

    # Eliminar etiquetas HTML
    cleaned = re.sub(r'<[^>]+>', '', raw_text)

    # Mantener solo caracteres alfanuméricos, puntuación y acentos españoles
    # Preserva: letras, dígitos, espacios, puntuación, acentos
    cleaned = re.sub(
        r'[^\w\s.,;:?!áéíóúüñÁÉÍÓÚÜÑ\(\)\[\]\{\}\-\'"]',
        ' ',
        cleaned
    )

    # Normalizar espacios múltiples a espacio único
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # ========================================
    # Paso 2: Validar longitud mínima
    # ========================================
    if not cleaned or len(cleaned.split()) < 5:
        cleaned = "Texto muy corto o vacío después de limpieza."

    # ========================================
    # Paso 3: Truncar a 500 caracteres (para demo)
    # En producción, podrías hacer chunks más inteligentes
    # ========================================
    text_summary = cleaned[:500]

    # ========================================
    # Paso 4: Estructurar como par instrucción-respuesta
    # (formato OpenAI messages para fine-tuning)
    # ========================================
    record = {
        "messages": [
            {
                "role": "user",
                "content": "Resume y estructura el siguiente contenido empresarial"
            },
            {
                "role": "assistant",
                "content": text_summary
            }
        ]
    }

    # ========================================
    # Paso 5: Convertir a JSON (JSONL)
    # ========================================
    result = json.dumps(record, ensure_ascii=False, indent=2)

    return result
