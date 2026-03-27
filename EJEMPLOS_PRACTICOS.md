# Ejemplos Prácticos - Agente LangChain Módulo II

## Caso de uso 1: Preparación de datos para fine-tuning

### Escenario
Tu empresa tiene un documento HTML de una política corporativa sin estructurar, y necesitas convertirlo a formato JSONL para entrenar un modelo.

### Implementación directa de la Tool

```python
from data_prep import data_prep_tool

# Documento HTML sin estructura
raw_documento = """
<html>
<body>
<h1>Política de Confidencialidad v3.2</h1>
<p>La empresa se compromete a proteger los datos personales de sus clientes.
Todo dato debe ser encriptado con AES-256. Los accesos se auditan mensualmente.</p>
<footer>© 2024 Empresa XYZ</footer>
</body>
</html>
"""

# Procesar con la tool
resultado = data_prep_tool.invoke({"raw_text": raw_documento})

print(resultado)
# Output: {"messages": [{"role": "user", "content": "Resume..."},
#                       {"role": "assistant", "content": "La empresa se compromete..."}]}

# Guardar en archivo JSONL para BigQuery
import json
with open("politica_limpia.jsonl", "w") as f:
    f.write(resultado + "\n")
```

### Conversación con el agente

```
Tú: Necesito limpiar este documento para fine-tuning:
<h1>Política de datos</h1>
<p>Los datos deben ser protegidos...</p>

🤔 Agente: El usuario pide limpiar un documento HTML...
          Usaré data_prep_tool

📤 Resultado: {
  "messages": [
    {"role": "user", "content": "Resume el siguiente texto empresarial:"},
    {"role": "assistant", "content": "Los datos deben ser protegidos..."}
  ]
}
```

---

## Caso de uso 2: Búsqueda en base de conocimiento

### Escenario
Un empleado necesita saber cuál es la política de datos de la empresa sin buscar manualmente en todos los documentos.

### Implementación directa de la Tool

```python
from rag_search import rag_search_tool

# Pregunta del usuario
pregunta = "¿Cuál es la política de datos de la empresa?"

# Buscar en base de conocimiento
resultado = rag_search_tool.invoke({"query": pregunta})

print(resultado)
# Output:
# 🔍 Resultados de búsqueda para: '¿Cuál es la política de datos de la empresa?'
#
# 📄 [Doc: Politica_Datos.pdf, pág. 2] Los datos de clientes deben ser
#    anonimizados mediante Cloud DLP antes de su procesamiento...
```

### Conversación con el agente

```
Tú: ¿Cuál es la política de datos de la empresa?

🤔 Agente: El usuario pregunta sobre políticas...
          Usaré rag_search_tool

📤 Resultado:
📄 [Doc: Politica_Datos.pdf]
Los datos de clientes deben ser anonimizados mediante Cloud DLP...

🤖 Respuesta final: Según la política de datos de la empresa,
todos los datos deben ser anonimizados usando Cloud DLP antes
de ser procesados o almacenados.
```

---

## Caso de uso 3: Protección de datos sensibles

### Escenario
Un equipo de soporte necesita procesar un email de cliente que contiene información personal, pero debe anonimizarla antes de agregarlo a un chat grupal.

### Implementación directa de la Tool

```python
from dlp_anonymizer import dlp_anonymizer_tool

# Email con datos sensibles
email_cliente = """
De: Juan Pérez García (DNI: 12345678)
Correo: juan.perez@empresa.com.pe
Teléfono: +51 987654321
Solicitud: Consulta sobre mi tarjeta 4532 1234 5678 9010
RUC: 20123456789

Tengo problemas con mi cuenta bancaria. ¿Pueden ayudarme?
"""

# Anonimizar antes de compartir
resultado = dlp_anonymizer_tool.invoke({"text": email_cliente})

print(resultado)
# Output:
# De: Juan Pérez García (DNI: [DNI])
# Correo: [EMAIL]
# Teléfono: [TELÉFONO]
# Solicitud: Consulta sobre mi tarjeta [TARJETA_CRÉDITO]
# RUC: [RUC]
#
# Tengo problemas con mi cuenta bancaria. ¿Pueden ayudarme?
```

### Conversación con el agente

```
Tú: Necesito anonimizar este email antes de compartirlo con el equipo:
De: Juan Pérez García (DNI: 12345678)
Correo: juan.perez@empresa.com.pe
...

🤔 Agente: El usuario necesita proteger PII...
          Usaré dlp_anonymizer_tool

📤 Resultado:
De: Juan Pérez García (DNI: [DNI])
Correo: [EMAIL]
...

🤖 Respuesta final: Email anonimizado correctamente.
Todos los datos sensibles han sido enmascarados.
Ahora es seguro compartir con el equipo.
```

---

## Flujo completo: Pipeline de datos

### Escenario
Una empresa recibe datos de clientes en HTML sin estructura. Necesita:
1. Limpiar los datos
2. Verificar si hay políticas aplicables
3. Anonimizar información sensible
4. Guardar para análisis

### Conversación con el agente

```
Tú: Tengo un documento de cliente en HTML que necesito procesar:
<html><body>
<h1>Cliente: Juan Pérez García</h1>
<p>DNI: 12345678, Email: juan@empresa.com</p>
<p>Contrato: Servicio Premium desde 2023</p>
</body></html>

Necesito: 1) Limpiarlo, 2) Verificar políticas, 3) Anonimizar.

🤔 Agente (Paso 1): El usuario pide limpiar datos...
          Usaré data_prep_tool

📤 Tool 1 Output:
{"messages": [{"role": "user", ...}, {"role": "assistant", "content": "Cliente: Juan..."}]}

🤔 Agente (Paso 2): Después de limpiar, busco políticas aplicables...
          Usaré rag_search_tool

📤 Tool 2 Output:
📄 [Doc: Politica_Datos.pdf] Los datos de clientes deben ser anonimizados...

🤔 Agente (Paso 3): Los datos contienen PII, usaré anonimización...
          Usaré dlp_anonymizer_tool

📤 Tool 3 Output:
Cliente: Juan Pérez García
DNI: [DNI], Email: [EMAIL]
Contrato: Servicio Premium desde 2023

🤖 Respuesta final: Proceso completado:
✅ Datos limpiados a formato JSONL
✅ Política de datos aplicable: anonimizar PII
✅ Información sensible enmascarada ([DNI], [EMAIL])
✅ Listo para almacenamiento seguro
```

---

## Ejemplo: Memoria en acción

### Conversación multi-turno

```
Turno 1:
Tú: ¿Cuál es la política de privacidad?
Agente: [usa rag_search_tool] → Devuelve política...

Turno 2:
Tú: ¿Y cómo se aplica específicamente a datos de clientes?
Agente: Recuerdo que previamente buscamos política de privacidad...
        [Usa contexto anterior + rag_search_tool]

Turno 3:
Tú: Limpia este email de cliente entonces
Agente: Recordando la política anterior + datos del email...
        [usa dlp_anonymizer_tool]

Turno 4:
Tú: ¿Qué hicimos hasta ahora?
Agente: [Consulta ConversationBufferWindowMemory]
        Hasta ahora hemos:
        1. Buscado la política de privacidad
        2. Aplicado a datos de clientes
        3. Anonimizado un email
```

**Nota:** La memoria mantiene los últimos 5 turnos, permitiendo que el agente tenga contexto.

---

## Extendiendo el agente: Agregar una 4ta herramienta

### Ejemplo: Tool para generar reportes

```python
# tools/report_generator.py
from langchain.tools import tool

@tool
def report_generator_tool(data: str, report_type: str) -> str:
    """
    Genera reportes ejecutivos basados en datos procesados.

    Úsala cuando el usuario necesite:
    - Resumen de datos procesados
    - Estadísticas de anonimización
    - Informe de compliance

    Args:
        data: Datos a reportar
        report_type: Tipo de reporte (summary, compliance, stats)

    Returns:
        Reporte formateado en markdown
    """
    if report_type == "summary":
        return f"""
        ## Resumen de procesamiento
        - Datos procesados: {len(data.split())} palabras
        - Registros: 1
        - Estado: ✅ Completado
        """
    elif report_type == "compliance":
        return f"""
        ## Reporte de Compliance
        ✅ Datos anonimizados según GDPR
        ✅ Auditoría realizada
        ✅ Registro en Cloud Logging
        """
    return "Reporte no disponible"


# Agregar a agent.py
from tools.report_generator import report_generator_tool

tools = [
    data_prep_tool,
    rag_search_tool,
    dlp_anonymizer_tool,
    report_generator_tool  # ← Nueva tool
]
```

### Uso en el agente

```
Tú: Después de procesar los datos, genera un reporte de compliance

🤔 Agente: El usuario pide un reporte...
          Usaré report_generator_tool

📤 Output:
## Reporte de Compliance
✅ Datos anonimizados según GDPR
✅ Auditoría realizada
✅ Registro en Cloud Logging
```

---

## Tips para el estudiante

### 1. Importancia de los docstrings
Los docstrings son **críticos**. El LLM los lee para decidir qué tool usar:

```python
# ❌ MAL - Docstring muy corto
@tool
def tool_incompleta(texto: str) -> str:
    """Procesa texto"""
    return texto

# ✅ BIEN - Docstring descriptivo
@tool
def tool_completa(texto: str) -> str:
    """
    Procesa y limpia texto corporativo.
    Elimina HTML, caracteres especiales y duplicados.

    Úsala cuando el usuario proporcione documentos sin estructurar
    que necesiten limpieza antes de análisis.
    """
    return texto
```

### 2. Variables de entorno
Nunca hardcodear información sensible:

```python
# ❌ MAL
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key="AIzaSyDaxxxxxxxxxx"  # ← ¡NO!
)

# ✅ BIEN
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=api_key
)
```

### 3. Manejo de errores
Usa `handle_parsing_errors=True` en AgentExecutor:

```python
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    handle_parsing_errors=True,  # ← Importante
    max_iterations=5
)
```

### 4. Verbose mode
Habilita durante desarrollo para ver el razonamiento:

```python
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True,  # ← Ver paso a paso cómo razona
    max_iterations=5
)
```

---

## Checklist para tu proyecto

- [ ] Clonar/descargar el código
- [ ] Crear `.env` con GOOGLE_API_KEY
- [ ] Instalar `pip install -r requirements.txt`
- [ ] Ejecutar `python test_agent.py` ✅
- [ ] Ejecutar `python agent.py` ✅
- [ ] Probar conversaciones multi-turno
- [ ] Extender con nuevas tools si necesitas
- [ ] Configurar GCP (opcional, para producción)
- [ ] Crear interfaz Streamlit (opcional)
- [ ] Generar informe técnico
- [ ] Crear presentación

---

¡Listo para presentar tu proyecto! 🎓
