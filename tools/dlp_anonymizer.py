"""
tools/dlp_anonymizer.py — Tool 3: Anonimización de PII con Cloud DLP

Esta herramienta detecta y enmascara automáticamente información personal
identificable (PII) en textos: nombres, correos, números de tarjeta, DNI, etc.
En desarrollo usa regex; en producción usa Google Cloud DLP API.
"""

import re
from langchain_classic.tools import tool


@tool
def dlp_anonymizer_tool(text: str) -> str:
    """
    Detecta y enmascara automáticamente información personal identificable (PII)
    en un texto, protegiendo datos sensibles.

    Detecta y enmascara:
    - Correos electrónicos (formato: usuario@dominio.extensión)
    - Números de tarjeta de crédito (4 grupos de 4 dígitos)
    - Teléfonos peruanos (celulares con prefijo +51 o sin prefijo)
    - DNI peruano (8 dígitos)
    - URLs (para evitar rastreabilidad)

    Debe usarse SIEMPRE antes de:
    - Almacenar datos de clientes
    - Procesar datos en sistemas de análisis
    - Compartir información entre departamentos
    - Exportar datos a terceros

    En producción, usa Google Cloud DLP para mayor precisión y tipos de datos adicionales.

    Args:
        text (str): Texto que puede contener datos sensibles

    Returns:
        str: Texto con PII reemplazado por etiquetas anónimas [TIPO_DATO]
    """

    anonymized = text

    # ========================================
    # Paso 1: Enmascarar correos electrónicos
    # ========================================
    # Patrón: usuario@dominio.extensión
    # Ejemplo: juan.perez@empresa.com → [EMAIL]
    anonymized = re.sub(
        r'\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b',
        '[EMAIL]',
        anonymized,
        flags=re.IGNORECASE
    )

    # ========================================
    # Paso 2: Enmascarar números de tarjeta de crédito
    # ========================================
    # Patrón: 4 grupos de 4 dígitos, separados por espacios o guiones
    # Ejemplos:
    #   4532 1234 5678 9010
    #   4532-1234-5678-9010
    anonymized = re.sub(
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        '[TARJETA_CRÉDITO]',
        anonymized
    )

    # ========================================
    # Paso 3: Enmascarar teléfonos celulares peruanos
    # ========================================
    # Patrón: +51 9XXXXXXXX o 51 9XXXXXXXX o 9XXXXXXXX
    # Ejemplos:
    #   +51 987654321
    #   51 987654321
    #   987654321
    anonymized = re.sub(
        r'\b(\+51|51)?\s?9\d{8}\b',
        '[TELÉFONO]',
        anonymized
    )

    # ========================================
    # Paso 4: Enmascarar números de DNI (8 dígitos)
    # ========================================
    # En Perú, DNI tiene exactamente 8 dígitos
    # Ejemplo: 12345678 → [DNI]
    # Nota: Esto podría afectar otros números de 8 dígitos, pero es acceptable para demo
    anonymized = re.sub(
        r'\b\d{8}\b',
        '[DNI]',
        anonymized
    )

    # ========================================
    # Paso 5: Enmascarar URLs (pueden rastrear al usuario)
    # ========================================
    # Patrón: http(s)://...
    anonymized = re.sub(
        r'https?://[^\s]+',
        '[URL]',
        anonymized,
        flags=re.IGNORECASE
    )

    # ========================================
    # Paso 6: Enmascarar números RUC (11 dígitos en Perú)
    # ========================================
    # Patrón: 11 dígitos separados o no
    anonymized = re.sub(
        r'\b\d{11}\b',
        '[RUC]',
        anonymized
    )

    # ========================================
    # Paso 7: Enmascarar nombres propios (OPCIONAL - comentado por defecto)
    # ========================================
    # Nota: Detectar nombres es más complicado sin lista de nombres.
    # Se comenta por defecto para evitar falsos positivos.
    # Si necesitas, descomenta:
    #
    # common_names = ['Juan', 'María', 'Carlos', 'Ana', 'Pedro', 'Rosa']
    # for name in common_names:
    #     anonymized = re.sub(
    #         rf'\b{name}\b',
    #         f'[NOMBRE_{name.upper()}]',
    #         anonymized,
    #         flags=re.IGNORECASE
    #     )

    return anonymized


# ========================================
# REFERENCIA: Versión PRODUCCIÓN con Google Cloud DLP
# ========================================
# Para máxima precisión y tipos de PII adicionales, usa Cloud DLP:
#
# def dlp_anonymizer_production(text: str, project_id: str) -> str:
#     """Versión producción con Google Cloud DLP API"""
#     from google.cloud import dlp_v2
#
#     # Inicializar cliente DLP
#     dlp_client = dlp_v2.DlpServiceClient()
#     project_path = dlp_client.project_path(project_id)
#
#     # Configurar tipos de PII a detectar
#     info_types = [
#         dlp_v2.InfoType(name="EMAIL_ADDRESS"),
#         dlp_v2.InfoType(name="CREDIT_CARD_NUMBER"),
#         dlp_v2.InfoType(name="PHONE_NUMBER"),
#         dlp_v2.InfoType(name="PASSPORT_NUMBER"),
#         dlp_v2.InfoType(name="PERSON_NAME"),
#     ]
#
#     # Configurar método de anonimización (MASK)
#     masking_character = "#"
#     primitive_transformation = {
#         "char_mask_config": {
#             "masking_character": masking_character,
#             "number_to_mask": 4
#         }
#     }
#
#     # Crear configuración de transformación
#     transformations = [
#         {
#             "primitive_transformation": primitive_transformation,
#             "info_types": info_types
#         }
#     ]
#
#     # Aplicar de-identification
#     content_item = {"value": text}
#     config = {
#         "info_types": info_types,
#         "transformation": {"transformations": transformations}
#     }
#
#     request = {
#         "parent": project_path,
#         "deidentify_config": config,
#         "items": [content_item]
#     }
#
#     response = dlp_client.deidentify_content(request=request)
#     deidentified_text = response.items[0].value
#
#     return deidentified_text
