# Proyecto Integrador Módulo II - Código Completo del Agente con LangChain

## 📋 Resumen

Te proporciono el **código completo y funcional** de un agente inteligente con LangChain que incluye:

✅ **3 herramientas personalizadas** completamente implementadas
✅ **AgentExecutor** configurado con memoria de conversación
✅ **Gemini 1.5 Flash** como LLM (vía google-generativeai)
✅ **Código listo para usar** sin dependencias externas innecesarias
✅ **Versiones mock** (desarrollo local) y referencias a versiones con GCP (producción)

---

## 🏗️ Estructura de archivos

```
proyecto-agente-modulo2/
├── agent.py                    ← Archivo principal (punto de entrada)
├── data_prep.py               ← Tool 1: Preparación de datos JSONL
├── rag_search.py              ← Tool 2: Búsqueda semántica RAG
├── dlp_anonymizer.py          ← Tool 3: Anonimización de PII
├── tools_init.py              ← __init__.py del paquete tools
├── test_agent.py              ← Pruebas unitarias
├── requirements.txt           ← Dependencias Python
├── .env.example               ← Plantilla de variables de entorno
└── README.md                  ← Documentación (opcional)
```

---

## 🔧 Las 3 Herramientas Personalizadas

### Tool 1: `data_prep_tool` — Preparación de datos para fine-tuning

**Propósito:** Limpiar texto corporativo crudo y convertirlo a formato JSONL listo para fine-tuning.

**Lo que hace:**
- Elimina HTML y caracteres especiales
- Normaliza espacios en blanco
- Estructura el texto como par instrucción-respuesta (messages format OpenAI)
- Devuelve JSON válido listo para BigQuery o datasets de LLM

**Ejemplo de uso:**
```python
from data_prep import data_prep_tool

raw_text = "<div>La empresa crecerá 15% en 2024</div>"
result = data_prep_tool.invoke({"raw_text": raw_text})
# Output: JSON con estructura {"messages": [{"role": "user", ...}, {"role": "assistant", ...}]}
```

---

### Tool 2: `rag_search_tool` — Búsqueda semántica en documentos corporativos

**Propósito:** Buscar información relevante en la base de conocimiento de la empresa usando RAG (Retrieval Augmented Generation).

**Lo que hace:**
- Busca fragmentos relevantes en documentos corporativos
- En desarrollo: retorna datos simulados (mock)
- En producción: se conecta a Vertex AI Vector Search Index
- Devuelve referencias de documento con fragmentos relevantes

**Ejemplo de uso:**
```python
from rag_search import rag_search_tool

query = "¿Cuál es la política de datos de la empresa?"
result = rag_search_tool.invoke({"query": query})
# Output: Fragmentos de documentos con referencias [Doc: ...]
```

---

### Tool 3: `dlp_anonymizer_tool` — Anonimización de datos sensibles (PII)

**Propósito:** Detectar y enmascarar información personal identificable (PII) automáticamente.

**Detecta y enmascara:**
- ✓ Correos electrónicos → `[EMAIL]`
- ✓ Números de tarjeta → `[TARJETA_CRÉDITO]`
- ✓ Teléfonos peruanos → `[TELÉFONO]`
- ✓ DNI (8 dígitos) → `[DNI]`
- ✓ RUC (11 dígitos) → `[RUC]`
- ✓ URLs → `[URL]`

**Ejemplo de uso:**
```python
from dlp_anonymizer import dlp_anonymizer_tool

text = "Mi DNI es 12345678 y mi correo es juan@empresa.com"
result = dlp_anonymizer_tool.invoke({"text": text})
# Output: "Mi DNI es [DNI] y mi correo es [EMAIL]"
```

---

## 🤖 Ensamblaje del AgentExecutor completo

El archivo `agent.py` contiene la configuración completa:

```python
from langchain.agents import AgentExecutor, create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.memory import ConversationBufferWindowMemory
from langchain import hub

# Importar tools
from data_prep import data_prep_tool
from rag_search import rag_search_tool
from dlp_anonymizer import dlp_anonymizer_tool

# 1. Configurar LLM (Gemini 1.5 Flash)
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key="TU_GOOGLE_API_KEY",
    temperature=0.1
)

# 2. Memoria de corto plazo (últimos 5 turnos)
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    k=5,
    return_messages=True
)

# 3. Lista de tools
tools = [data_prep_tool, rag_search_tool, dlp_anonymizer_tool]

# 4. Prompt del agente (ReAct pattern)
prompt = hub.pull("hwchase17/react-chat")

# 5. Crear agente
agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)

# 6. Ejecutor con manejo de errores
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=5
)

# 7. Usar el agente
response = agent_executor.invoke({"input": "Tu pregunta aquí"})
print(response['output'])
```

---

## 🚀 Guía de instalación y ejecución

### Paso 1: Clonar / Descargar el código

```bash
# O copiar los archivos proporcionados
ls -la
# Deberías ver: agent.py, data_prep.py, rag_search.py, dlp_anonymizer.py, requirements.txt, etc.
```

### Paso 2: Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### Paso 3: Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 4: Configurar variables de entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar .env y agregar tu GOOGLE_API_KEY
# GOOGLE_API_KEY=tu_clave_aqui
```

**¿Dónde obtener GOOGLE_API_KEY?**
1. Ir a https://aistudio.google.com/app/apikeys
2. Crear una nueva clave API
3. Copiar en tu archivo `.env`

### Paso 5: Ejecutar pruebas

```bash
# Probar cada tool individualmente
python test_agent.py

# Output esperado:
# ✅ TEST 1: data_prep_tool → PASSED
# ✅ TEST 2: rag_search_tool → PASSED
# ✅ TEST 3: dlp_anonymizer_tool → PASSED
```

### Paso 6: Ejecutar el agente

```bash
python agent.py

# Output:
# ===========================================================================
# 🤖 Agente IA - Proyecto Integrador Módulo II
# ===========================================================================
# Herramientas disponibles:
#   1. data_prep_tool     → Limpia y convierte texto a JSONL
#   2. rag_search_tool    → Busca en documentos corporativos
#   3. dlp_anonymizer_tool → Enmascara datos sensibles (PII)
#
# Escribe 'salir' para terminar.
# ===========================================================================
#
# Tú: _
```

---

## 💬 Ejemplos de uso del agente

### Ejemplo 1: Preparar datos

```
Tú: Necesito limpiar este texto: "<div>La empresa tiene 500 empleados</div>"

Agente: [Usa data_prep_tool]
Output: {"messages": [...]}
```

### Ejemplo 2: Buscar en documentos

```
Tú: ¿Cuál es la política de datos de la empresa?

Agente: [Usa rag_search_tool]
Output: 📄 [Doc: Politica_Datos.pdf] Los datos deben ser anonimizados...
```

### Ejemplo 3: Proteger datos sensibles

```
Tú: Necesito anonimizar este texto: "DNI 12345678, correo juan@empresa.com"

Agente: [Usa dlp_anonymizer_tool]
Output: "DNI [DNI], correo [EMAIL]"
```

---

## 🔑 Conceptos clave

### ReAct Pattern
El agente usa el patrón **ReAct (Reasoning + Acting)**:
1. **Lee** la pregunta del usuario
2. **Razona** qué herramienta usar basándose en los docstrings
3. **Actúa** ejecutando la herramienta seleccionada
4. **Observa** el resultado
5. **Repite** hasta resolver la pregunta

### ConversationBufferWindowMemory
- Mantiene los **últimos 5 turnos** de conversación
- Permite que el agente tenga contexto
- Evita consumir demasiados tokens

### Docstrings críticos
Los docstrings de cada tool son **cruciales** porque el LLM los lee para decidir cuándo usar cada herramienta:

```python
@tool
def data_prep_tool(raw_text: str) -> str:
    """
    Limpia y transforma texto corporativo...  ← El LLM LEE ESTO
    Úsala cuando...                            ← Instrucciones de cuándo usar
    """
```

---

## 📚 Archivos incluidos

| Archivo | Descripción |
|---------|-----------|
| `agent.py` | Punto de entrada principal - configura el AgentExecutor |
| `data_prep.py` | Tool 1 con lógica de limpieza y estructuración JSONL |
| `rag_search.py` | Tool 2 con búsqueda simulada (mock) y referencias a GCP |
| `dlp_anonymizer.py` | Tool 3 con patrones regex para detectar/enmascarar PII |
| `tools_init.py` | `__init__.py` para importar todas las tools |
| `test_agent.py` | Suite de pruebas unitarias para cada tool |
| `requirements.txt` | Dependencias Python necesarias |
| `.env.example` | Plantilla de variables de entorno |
| `response.md` | Este archivo (documentación) |

---

## 🔧 Personalización y extensión

### Agregar una nueva Tool

1. Crear archivo `tools/nueva_tool.py`:
```python
from langchain.tools import tool

@tool
def nueva_tool(param: str) -> str:
    """
    Descripción clara de qué hace esta herramienta.
    Cuándo usar: [instrucciones para el LLM]
    """
    # tu lógica aquí
    return resultado
```

2. Agregar a `agent.py`:
```python
from tools.nueva_tool import nueva_tool

tools = [data_prep_tool, rag_search_tool, dlp_anonymizer_tool, nueva_tool]
```

### Cambiar el modelo LLM

```python
# De Gemini Flash a Gemini Pro
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",  # ← Cambiar aquí
    google_api_key=api_key,
    temperature=0.1
)
```

### Aumentar memoria

```python
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    k=10,  # Mantener últimos 10 turnos en lugar de 5
    return_messages=True
)
```

---

## 🚨 Solución de problemas

### Error: "No se encontró GOOGLE_API_KEY"
**Solución:** Crear archivo `.env` con:
```
GOOGLE_API_KEY=tu_clave_aqui
```

### Error: "Module 'tools' not found"
**Solución:** Renombrar `tools_init.py` a `__init__.py` en carpeta `tools/`:
```bash
mkdir tools
mv data_prep.py rag_search.py dlp_anonymizer.py tools/
mv tools_init.py tools/__init__.py
```

### Las tools no se invocan
**Causa:** Docstrings insuficientes. El LLM necesita instrucciones claras en los docstrings de cuándo usar cada tool.

---

## 📊 Arquitectura del sistema

```
┌─────────────────┐
│   Usuario       │
│  (prompt)       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              AgentExecutor (LangChain)                  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  LLM (Gemini 1.5 Flash)                          │  │
│  │  - Lee el prompt                                 │  │
│  │  - Decide qué tool usar                          │  │
│  │  - Genera respuesta final                        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Memory (ConversationBufferWindowMemory)         │  │
│  │  - Mantiene últimos 5 turnos                     │  │
│  │  - Proporciona contexto al LLM                   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Tools                                           │  │
│  │  ├─ data_prep_tool       → JSONL                 │  │
│  │  ├─ rag_search_tool      → Documentos           │  │
│  │  └─ dlp_anonymizer_tool  → PII                  │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Respuesta      │
│  Final          │
└─────────────────┘
```

---

## 📝 Notas importantes

1. **Desarrollo vs Producción:**
   - Las tools usan **mock data** por defecto (sin GCP real)
   - En producción, reemplazar mocks con llamadas reales a Vertex AI / Cloud DLP
   - Los comentarios en el código indican dónde hacer cambios

2. **Seguridad:**
   - Nunca hardcodear API keys en el código
   - Usar `.env` y `.gitignore`
   - La tool `dlp_anonymizer` es fundamental antes de procesar datos

3. **Costo:**
   - Usa `gemini-1.5-flash` (más barato) en desarrollo
   - Usa `gemini-1.5-pro` solo para demos finales
   - Cada invocación de tool incurre en tokens

4. **Escalabilidad:**
   - Para producción, considera usar Cloud Run para el agente
   - Integra con Streamlit o FastAPI para UI
   - Usa Cloud Logging para monitoreo

---

## 🎯 Próximos pasos del proyecto

1. ✅ Código de tools (HECHO - este documento)
2. Configurar GCP (Vertex AI Vector Search, Cloud DLP)
3. Crear interfaz web (Streamlit o Gradio)
4. Generar informe técnico (Word)
5. Crear presentación (PowerPoint)
6. Publicar en Cloud Run (opcional)

---

## 📞 Soporte

Si necesitas ayuda:
- Revisa los **comentarios en el código** (explicaciones línea por línea)
- Ejecuta **`test_agent.py`** para verificar que todo funciona
- Consulta la **[documentación oficial de LangChain](https://python.langchain.com/)**
- Verifica tu **GOOGLE_API_KEY** en https://aistudio.google.com/app/apikeys

---

**¡Listo para empezar! 🚀**

Todos los archivos están listos para usar. Solo necesitas:
1. Crear `.env` con tu GOOGLE_API_KEY
2. Ejecutar `pip install -r requirements.txt`
3. Ejecutar `python agent.py`

¡Éxito con tu Proyecto Integrador Módulo II! 🎓
