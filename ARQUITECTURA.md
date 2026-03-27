# Arquitectura del Agente - Módulo II

## 1. Flujo general del agente

```
┌─────────────────────────────────────────────────────────────────┐
│                         USUARIO                                 │
│                    (Escribe pregunta)                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INPUT PROCESSING                            │
│                                                                 │
│  1. Recibir prompt del usuario                                 │
│  2. Recuperar historial de memoria (últimos 5 turnos)         │
│  3. Construir contexto para el LLM                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              LLM REASONING (Gemini 1.5 Flash)                  │
│                                                                 │
│  ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁  │
│  Prompt recibido: "Limpia este HTML: <div>..."               │
│                                                                 │
│  Analizando docstrings de tools disponibles:                  │
│  ✓ data_prep_tool:        "Limpia texto crudo a JSONL"      │
│  ✓ rag_search_tool:       "Busca en documentos"              │
│  ✓ dlp_anonymizer_tool:   "Enmascara PII"                    │
│                                                                 │
│  Razonamiento: El usuario menciona "limpia HTML"              │
│  → data_prep_tool es la más apropiada ✅                      │
│  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TOOL EXECUTION                               │
│                                                                 │
│  Ejecutar: data_prep_tool(raw_text="<div>...")               │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ data_prep_tool:                                          │ │
│  │ 1. Elimina HTML: <div> → ""                             │ │
│  │ 2. Normaliza espacios                                    │ │
│  │ 3. Estructura como messages: {                           │ │
│  │      "messages": [                                       │ │
│  │        {"role": "user", "content": "Resume..."},        │ │
│  │        {"role": "assistant", "content": "..."}          │ │
│  │      ]                                                   │ │
│  │    }                                                     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Retornar resultado a LLM                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│               OBSERVATION & RESPONSE GENERATION                │
│                                                                 │
│  Tool resultado: {JSON limpio}                                │
│                                                                 │
│  LLM genera respuesta final:                                  │
│  "He limpiado el HTML y lo he estructurado en formato JSONL  │
│   listo para fine-tuning. El contenido ha sido normalizado   │
│   y está en el formato messages estándar."                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│               MEMORY UPDATE & OUTPUT                            │
│                                                                 │
│  1. Guardar en memoria:                                       │
│     - User input: "Limpia este HTML: <div>..."              │
│     - Assistant output: "He limpiado..."                     │
│                                                                 │
│  2. Devolver respuesta al usuario                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OUTPUT (Usuario ve)                          │
│                                                                 │
│  Agente: "He limpiado el HTML y lo he estructurado en        │
│           formato JSONL listo para fine-tuning..."          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Componentes principales

### 2.1 LLM (Gemini 1.5 Flash)

```python
┌──────────────────────────────────────────┐
│        ChatGoogleGenerativeAI            │
├──────────────────────────────────────────┤
│ - Model: gemini-1.5-flash               │
│ - Temperature: 0.1 (determinístico)      │
│ - API Key: vía google-generativeai       │
└──────────────────────────────────────────┘
         ▲              │
         │              ▼
   Requiere API Key   Lee docstrings
                      de tools para
                      tomar decisiones
```

**¿Por qué Gemini 1.5 Flash?**
- ✅ Rápido
- ✅ Económico (mejor costo)
- ✅ Excelente para tasks intermedias
- ✅ Modelos Gemini Pro disponibles para prod

### 2.2 Memory (ConversationBufferWindowMemory)

```python
┌────────────────────────────────────────────────────────┐
│     ConversationBufferWindowMemory(k=5)               │
├────────────────────────────────────────────────────────┤
│ Mantiene los últimos 5 turnos:                        │
│                                                        │
│ Turno 5 (actual):    User → Agente                   │
│ Turno 4:             User → Agente                   │
│ Turno 3:             User → Agente                   │
│ Turno 2:             User → Agente                   │
│ Turno 1 (anterior):  User → Agente                   │
│                                                        │
│ Turno 0 (olvidado):  X (fuera de memoria)            │
└────────────────────────────────────────────────────────┘
```

**Ventajas:**
- Contexto sin consumir demasiados tokens
- Balance entre memoria y costo
- Suficiente para conversations naturales

### 2.3 Tools (3 herramientas)

```
┌──────────────────────────────────────────────────────────┐
│                   TOOLS DISPONIBLES                      │
└──────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌──────────┐      ┌─────────────┐
   │ Tool 1  │      │ Tool 2   │      │ Tool 3      │
   │ ───────│      │ ────────│      │ ─────────────│
   │data_prep│      │rag_      │      │dlp_         │
   │ _tool   │      │search_   │      │anonymizer_  │
   │         │      │tool      │      │tool         │
   └────┬────┘      └────┬─────┘      └──────┬──────┘
        │                │                   │
        ▼                ▼                   ▼
   Entrada:         Entrada:           Entrada:
   raw_text         query              text
   (HTML,etc)       (pregunta)         (con PII)
        │                │                   │
        ▼                ▼                   ▼
   Procesa:         Procesa:           Procesa:
   - Limpia HTML    - Busca en docs   - Detecta PII
   - Normaliza      - Retorna refs    - Enmascara
   - Estructura     - Textos          - Regex/DLP
   - JSON           - Similitud
        │                │                   │
        ▼                ▼                   ▼
   Salida:          Salida:            Salida:
   JSONL limpio     Documentos         Texto
   {messages}       relevantes         anonimizado
```

---

## 3. Flujo del ReAct Pattern

```
┌─────────────────────────────────────────────────────────┐
│              ReAct: Reasoning + Acting                  │
└─────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────┐
    │  THINK (Pensar)                              │
    │  ────────────────────────────────────────    │
    │  El LLM analiza la pregunta                 │
    │  Lee los docstrings de las tools            │
    │  Decide cuál es la más apropiada             │
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │  ACT (Actuar)                               │
    │  ────────────────────────────────────────    │
    │  Ejecuta la tool seleccionada              │
    │  Procesa los parámetros                     │
    │  Retorna resultado                          │
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │  OBSERVE (Observar)                         │
    │  ────────────────────────────────────────    │
    │  El LLM recibe el resultado                 │
    │  Interpreta los datos                       │
    │  Decide si:                                 │
    │  - Responder directamente, o                │
    │  - Usar otra tool, o                        │
    │  - Usar más iteraciones                     │
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │  LOOP (Repetir hasta max_iterations)        │
    │  ────────────────────────────────────────    │
    │  Si no se resolvió: volver a THINK           │
    │  Si se resolvió: generar respuesta final    │
    └──────────────────────────────────────────────┘
```

---

## 4. Estructura del código

```
agent.py (Punto de entrada)
    │
    ├─► setup_agent()
    │   ├─► Configura LLM (Gemini)
    │   ├─► Crea Memory
    │   ├─► Importa Tools
    │   ├─► Carga prompt (hub.pull)
    │   ├─► Crea ReAct agent
    │   └─► Retorna AgentExecutor
    │
    └─► main()
        ├─► Llama setup_agent()
        └─► Bucle while True
            ├─► Lee input usuario
            ├─► Invoca agent_executor.invoke()
            │   └─► Ocurre la magia (ReAct)
            └─► Imprime respuesta
```

---

## 5. Flujo de datos en una conversación

```
TURNO 1:
┌────────────────┐
│ User: "Limpia  │
│  este HTML"    │
└────────┬───────┘
         │
         ▼
    [Memory vacía]
    [LLM analiza]
    [Elige: data_prep_tool]

    ▼ RESULTADO
    [JSON limpio]

    Memory ahora contiene:
    - Turno 1: user + assistant


TURNO 2:
┌────────────────┐
│ User: "Ahora   │
│  busca en docs"│
└────────┬───────┘
         │
         ▼
    [Memory con Turno 1]
    [LLM analiza con contexto anterior]
    [Elige: rag_search_tool]

    ▼ RESULTADO
    [Documentos relevantes]

    Memory ahora contiene:
    - Turno 1: ... (olvidado del buffer)
    - Turno 2: user + assistant


TURNO 3:
┌──────────────────────┐
│ User: "Anonimiza eso"│
└────────┬─────────────┘
         │
         ▼
    [Memory con Turnos 2-3]
    [LLM entiende "eso" = documentos]
    [Elige: dlp_anonymizer_tool]

    ▼ RESULTADO
    [Texto anonimizado]

    Memory contiene:
    - Turno 3: user + assistant
```

---

## 6. Integración con GCP (Producción)

```
┌──────────────────────────────────────────────────────┐
│  VERSIÓN DESARROLLO (Actual - Mock)                 │
│                                                      │
│  rag_search_tool → Mock data (documentos simulados) │
│  dlp_anonymizer_tool → Regex patterns (local)       │
└──────────────────────────────────────────────────────┘
                        ▼
            (Fácil de desarrollar y probar)


┌──────────────────────────────────────────────────────┐
│  VERSIÓN PRODUCCIÓN (con GCP real)                  │
│                                                      │
│  rag_search_tool ─────────────────┐                 │
│    └─► Vertex AI Vector Search    │                 │
│         └─► Embeddings via        │                 │
│             TextEmbeddingModel    │                 │
│                                   ├─► Google Cloud  │
│  dlp_anonymizer_tool ────────────┤   Platform      │
│    └─► Cloud DLP API             │                 │
│         └─► detectInfoTypes()    │                 │
│         └─► deidentifyContent()  │                 │
│                                   │
│  data_prep_tool ────────────────┤
│    └─► BigQuery ML               │
│         └─► JSONL format          │
└──────────────────────────────────┴──────────────────┘
```

---

## 7. Dependencias y relaciones

```
requirements.txt
    ├─► langchain==0.3.0
    │   └─► Crea agents, tools, memory
    │
    ├─► langchain-google-genai==2.0.0
    │   └─► ChatGoogleGenerativeAI (LLM)
    │
    ├─► google-cloud-aiplatform==1.60.0
    │   └─► (Opcional) Vertex AI en producción
    │
    ├─► google-cloud-dlp==3.20.0
    │   └─► (Opcional) Cloud DLP en producción
    │
    ├─► google-generativeai==0.8.1
    │   └─► API para Gemini
    │
    ├─► python-dotenv==1.0.0
    │   └─► Cargar .env (API keys)
    │
    └─► streamlit==1.38.0
        └─► (Opcional) UI web
```

---

## 8. Ciclo de vida del AgentExecutor

```
┌─────────────────────────────────────────────────────┐
│         agent_executor.invoke()                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. INPUT                                          │
│     └─► Recibe {"input": "pregunta del usuario"}  │
│                                                     │
│  2. MEMORY RETRIEVAL                               │
│     └─► Obtiene últimos 5 turnos                  │
│                                                     │
│  3. CONTEXT BUILDING                               │
│     └─► Construye prompt con contexto + pregunta  │
│                                                     │
│  4. LLM CALL                                       │
│     └─► Envía a Gemini                            │
│                                                     │
│  5. TOOL SELECTION                                 │
│     └─► LLM decide qué tool usar                  │
│                                                     │
│  6. LOOP (hasta max_iterations=5)                 │
│     ├─► TOOL EXECUTION                            │
│     │   └─► Ejecuta tool seleccionada             │
│     │                                              │
│     ├─► OBSERVATION                               │
│     │   └─► LLM observa resultado                 │
│     │                                              │
│     └─► DECISION                                  │
│         ├─► ¿Responder?  → Final answer            │
│         ├─► ¿Otra tool?  → Volver a step 5        │
│         └─► ¿Error?      → handle_parsing_errors   │
│                                                     │
│  7. MEMORY UPDATE                                  │
│     └─► Guarda user input + respuesta en memory   │
│                                                     │
│  8. OUTPUT                                         │
│     └─► Retorna {"output": "respuesta final"}     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 9. Diagrama de decisión del LLM

```
Pregunta del usuario
         │
         ▼
¿Contiene palabras como "limpia", "HTML", "datos"?
    ├─ SÍ ──► Usar data_prep_tool
    └─ NO ──┐
           │
           ▼
    ¿Contiene "busca", "política", "documento", "manual"?
        ├─ SÍ ──► Usar rag_search_tool
        └─ NO ──┐
               │
               ▼
        ¿Contiene "anonimiza", "PII", "datos sensibles", "email", "DNI"?
            ├─ SÍ ──► Usar dlp_anonymizer_tool
            └─ NO ──┐
                   │
                   ▼
            Responder sin tools
            (Conversación general)
```

---

## 10. Matriz de decisión: Cuándo usar cada tool

| Situación | Tool | Por qué |
|-----------|------|--------|
| "Limpia este HTML" | data_prep_tool | Docstring: "Limpia texto crudo" |
| "¿Cuál es la política?" | rag_search_tool | Docstring: "Busca documentos" |
| "Anonimiza el email" | dlp_anonymizer_tool | Docstring: "Enmascara PII" |
| "Convierte a JSONL" | data_prep_tool | Docstring: "formato JSONL" |
| "¿Qué dice el manual?" | rag_search_tool | Docstring: "documento interno" |
| "Protege DNI/emails" | dlp_anonymizer_tool | Docstring: "detecta PII" |

---

**Conclusión:** La arquitectura es modular, escalable y fácil de extender. Cada herramienta tiene un propósito claro, y el agente (mediante ReAct) es capaz de razonar y elegir la correcta automáticamente.
