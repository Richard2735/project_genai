# 🤖 Agente Inteligente con LangChain - Proyecto Integrador Módulo II

## Inicio rápido

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Configurar API Key
```bash
# Copiar plantilla
cp .env.example .env

# Editar .env y agregar tu GOOGLE_API_KEY
# Obtén la clave en: https://aistudio.google.com/app/apikeys
```

### 3. Ejecutar pruebas
```bash
python test_agent.py
```

### 4. Ejecutar el agente
```bash
python agent.py
```

## Archivos principales

- **`agent.py`** - Punto de entrada (AgentExecutor + bucle de conversación)
- **`data_prep.py`** - Tool 1: Limpieza de datos a JSONL
- **`rag_search.py`** - Tool 2: Búsqueda en documentos corporativos
- **`dlp_anonymizer.py`** - Tool 3: Anonimización de PII
- **`test_agent.py`** - Pruebas unitarias de las tools
- **`response.md`** - Documentación completa

## Las 3 herramientas

| Tool | Función | Ejemplo |
|------|---------|---------|
| `data_prep_tool` | Limpia HTML y estructura JSONL | Prepara datos para fine-tuning |
| `rag_search_tool` | Busca en documentos corporativos | Encuentra políticas y manuales |
| `dlp_anonymizer_tool` | Enmascara datos sensibles | Protege DNI, emails, tarjetas |

## Ejemplos de uso

```python
from agent import setup_agent

agent_executor = setup_agent()

# El agente elige automáticamente qué tool usar
response = agent_executor.invoke({
    "input": "Limpia este HTML: <div>Empresa</div>"
})
print(response['output'])
```

## Estructura del proyecto

```
.
├── agent.py                # Agente principal
├── data_prep.py           # Tool 1
├── rag_search.py          # Tool 2
├── dlp_anonymizer.py      # Tool 3
├── test_agent.py          # Tests
├── requirements.txt       # Dependencias
├── .env.example           # Plantilla .env
├── response.md            # Documentación detallada
└── README.md              # Este archivo
```

## Memoria del agente

- Mantiene los **últimos 5 turnos** de conversación
- Permite que el agente tenga contexto entre preguntas
- Usa `ConversationBufferWindowMemory` de LangChain

## Próximos pasos

1. Obtener GOOGLE_API_KEY en https://aistudio.google.com/app/apikeys
2. Crear `.env` con tu clave
3. Ejecutar `python test_agent.py` para validar
4. Ejecutar `python agent.py` e interactuar con el agente
5. En producción: conectar con Vertex AI y Cloud DLP reales

## Documentación

Lee **`response.md`** para:
- Explicación detallada de cada tool
- Arquitectura del sistema
- Guía de extensión
- Solución de problemas
- Ejemplos de uso completos

---

**¡Lista para usar! 🚀**
# project_genai
