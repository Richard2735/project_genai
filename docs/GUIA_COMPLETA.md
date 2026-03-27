# Guía Completa — Proyecto Integrador Módulo II

Documentación técnica detallada del agente inteligente con LangChain + GCP.

## Contenido

- Arquitectura del sistema → ver `ARQUITECTURA.md` en la raíz del proyecto
- Ejemplos de uso → ver `EJEMPLOS_PRACTICOS.md`
- Checklist de entrega → ver `CHECKLIST_ENTREGA.md`
- Índice general → ver `INDICE.md`

## Flujo de ejecución

1. El usuario escribe una pregunta
2. `AgentExecutor` recibe el input junto con el historial de memoria (últimos 5 turnos)
3. El LLM (Gemini 1.5 Flash) razona y selecciona la tool más apropiada leyendo sus docstrings
4. La tool se ejecuta y retorna el resultado
5. El LLM genera la respuesta final y la memoria se actualiza

## Cómo agregar una nueva tool

```python
# tools/mi_nueva_tool.py
from langchain.tools import tool

@tool
def mi_nueva_tool(parametro: str) -> str:
    """
    Descripción clara en español de qué hace esta tool.
    El agente lee este docstring para decidir cuándo usarla.

    Args:
        parametro (str): Descripción del parámetro

    Returns:
        str: Descripción del resultado
    """
    # Implementación
    return resultado
```

Luego agregar en `agent.py`:
```python
from tools.mi_nueva_tool import mi_nueva_tool
tools = [data_prep_tool, rag_search_tool, dlp_anonymizer_tool, mi_nueva_tool]
```

## Migración a GCP

Cada tool tiene comentarios `# En producción usar:` con el código equivalente usando:
- `data_prep_tool` → Cloud Dataflow + BigQuery ML
- `rag_search_tool` → Vertex AI Vector Search
- `dlp_anonymizer_tool` → Cloud DLP API
