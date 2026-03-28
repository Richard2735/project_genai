# Mejoras de Arquitectura Propuestas — Roadmap v2.0

Documento de mejoras y evoluciones propuestas para llevar el proyecto al siguiente nivel de madurez, escalabilidad y funcionalidad.

---

## 1. Mejoras al Pipeline RAG

### 1.1 HyDE (Hypothetical Document Embeddings)

**Estado actual:** La query del usuario se vectoriza directamente y se busca en FAISS.

**Mejora:** Antes de buscar, el LLM genera un "documento hipotetico" que responderia la pregunta. Se vectoriza esa hipotesis (que tiene vocabulario mas similar a los documentos reales) y se usa para la busqueda semantica.

```
Query usuario
    |
    v
LLM genera respuesta hipotetica (sin RAG)
    |
    v
Embedding de la hipotesis
    |
    v
FAISS search (Top-K) -- mayor precision
    |
    v
Chunks reales + LLM --> Respuesta final
```

**Impacto:** Mejora la relevancia de resultados en queries ambiguas o cortas.

**Implementacion:**
- Archivo: `tools/rag_search.py`
- Agregar flag `USE_HYDE=true` en configuracion
- Usar `ChatVertexAI` para generar la hipotesis antes del embedding

### 1.2 Re-ranking con Cross-Encoder

**Estado actual:** FAISS retorna los Top-K chunks por similitud coseno pura.

**Mejora:** Despues del retrieval inicial (Top-20), aplicar un cross-encoder (ej: `cross-encoder/ms-marco-MiniLM-L-6-v2`) que re-rankea los resultados considerando la relacion query-documento completa.

```
FAISS Top-20 --> Cross-Encoder Re-rank --> Top-5 finales --> LLM
```

**Impacto:** Mayor precision en los chunks seleccionados, especialmente para queries complejas.

### 1.3 Chunking Semantico (en vez de por caracteres)

**Estado actual:** Los documentos se fragmentan en chunks de 500 caracteres con overlap de 100.

**Mejora:** Usar chunking semantico que divide por secciones logicas del documento (titulos, subtitulos, parrafos completos) en lugar de cortes arbitrarios por longitud.

**Opciones:**
- `langchain.text_splitter.MarkdownHeaderTextSplitter` para documentos con estructura
- Modelos de segmentacion semantica que detectan cambios de tema

### 1.4 Vertex AI Vector Search (reemplazo de FAISS)

**Estado actual:** FAISS como indice local, serializado a GCS.

**Mejora:** Migrar a **Vertex AI Vector Search** (managed service):
- Escalabilidad automatica (millones de vectores)
- Busqueda ANN (Approximate Nearest Neighbor) optimizada
- Filtros de metadatos nativos
- Sin necesidad de descargar el indice al Service

```
Estado actual:                      Propuesto:
GCS -> descarga FAISS -> memoria    Vertex AI Vector Search (managed)
                                    |
                                    API call directo desde Cloud Run
```

**Consideracion:** Mayor costo ($0.60/GB/mes) pero elimina la latencia de descarga del indice.

---

## 2. Mejoras al Agente

### 2.1 Multi-Agent Architecture

**Estado actual:** Un solo AgentExecutor con 3 tools.

**Mejora:** Arquitectura multi-agente con agentes especializados:

```
┌─────────────────────────────────────────────────┐
│              Agente Orquestador                  │
│         (Router / Supervisor Agent)              │
├──────────┬──────────────┬───────────────────────┤
│          │              │                       │
v          v              v                       v
Agente     Agente         Agente              Agente
RAG        Data Prep      Compliance          Resumen
│          │              │                       │
├─Search   ├─ Clean       ├─ DLP Anonymize        ├─ Summarize
├─ Cite    ├─ JSONL       ├─ Policy Check         ├─ Translate
└─ Filter  └─ Validate    └─ Audit Log            └─ Compare
```

**Framework:** Migrar de `AgentExecutor` a **LangGraph** para flujos de agentes mas complejos con estados y transiciones.

### 2.2 Memoria Persistente (PostgreSQL / Firestore)

**Estado actual:** Memoria en RAM con ventana de k=5 turnos. Se pierde al reiniciar el contenedor.

**Mejora:** Persistir las conversaciones en **Cloud Firestore** o **Cloud SQL (PostgreSQL)**:
- Historial completo por usuario/sesion
- Analytics sobre preguntas frecuentes
- Feedback loop para mejorar el agente

### 2.3 Streaming de Respuestas

**Estado actual:** El backend espera la respuesta completa del LLM y la envia de una vez.

**Mejora:** Implementar **Server-Sent Events (SSE)** o **WebSockets** para streaming token por token:

```
Frontend <--- SSE stream --- FastAPI <--- LLM streaming --- Gemini
```

**Impacto:** Mejor UX, el usuario ve la respuesta generandose en tiempo real.

---

## 3. Mejoras de Infraestructura

### 3.1 CI/CD Completo con GitHub Actions

**Estado actual:** Cloud Build trigger manual con `cloudbuild.yaml`.

**Mejora:** Pipeline CI/CD completo con GitHub Actions:

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]

jobs:
  test:
    - run: python test_agent.py

  build-and-deploy:
    needs: test
    - Build Docker images
    - Push to Artifact Registry (via Workload Identity Federation)
    - Deploy to Cloud Run
    - Run smoke tests
    - Notify on Slack
```

**Beneficios:**
- Tests automaticos antes de deploy
- Workload Identity Federation (sin JSON keys)
- Deploy automatico al hacer merge a main
- Rollback automatico si los smoke tests fallan

### 3.2 Terraform / Infrastructure as Code

**Estado actual:** Infraestructura creada manualmente con `gcloud` CLI.

**Mejora:** Definir toda la infraestructura en **Terraform**:

```
infrastructure/
├── main.tf              # Provider, proyecto
├── cloud_run.tf         # Service + Job
├── storage.tf           # Bucket GCS
├── iam.tf               # Service Accounts + roles
├── secret_manager.tf    # Secretos
├── artifact_registry.tf # Repo de imagenes
└── document_ai.tf       # Procesador OCR
```

**Beneficios:**
- Reproducibilidad total del entorno
- Versionamiento de infraestructura
- Facilita crear ambientes (dev, staging, prod)

### 3.3 Monitoreo y Observabilidad

**Estado actual:** Solo logs basicos en Cloud Logging.

**Mejora:** Stack de observabilidad completo:

| Componente | Herramienta | Que monitorea |
|---|---|---|
| **Metricas** | Cloud Monitoring | Latencia, errores, throughput API |
| **Logs** | Cloud Logging + Log Router | Logs estructurados del agente |
| **Traces** | Cloud Trace | Latencia end-to-end (API → LLM → respuesta) |
| **Dashboards** | Grafana / Looker Studio | KPIs: preguntas/dia, tiempo de respuesta, satisfaccion |
| **Alertas** | Cloud Monitoring Alerts | Error rate > 5%, latencia > 10s, OOM |

### 3.4 Autenticacion de Usuarios

**Estado actual:** API publica sin autenticacion (`--allow-unauthenticated`).

**Mejora:** Implementar autenticacion con **Firebase Auth** o **Identity Platform**:
- Login con Google / email
- Tokens JWT en cada request
- Rate limiting por usuario
- Roles: admin, usuario, viewer

---

## 4. Mejoras al Frontend

### 4.1 Feedback del Usuario

Agregar botones de like/dislike en cada respuesta del agente:
- Almacenar feedback en Firestore
- Usar para fine-tuning del prompt
- Dashboard de satisfaccion

### 4.2 Citacion de Fuentes con Links

**Estado actual:** El agente menciona las fuentes pero sin links directos.

**Mejora:** Mostrar las fuentes como cards clicables con:
- Nombre del documento
- Pagina especifica
- Score de relevancia
- Preview del chunk usado

### 4.3 Upload de Documentos

Permitir que los usuarios suban nuevos PDFs desde el frontend:
- Upload → GCS → trigger ingesta incremental → actualizar indice FAISS
- Validacion de formato y tamano
- Cola de procesamiento con Cloud Tasks

### 4.4 Modo Comparacion

Mostrar resultados de multiples documentos lado a lado cuando la pregunta aplica a varias politicas/procedimientos.

---

## 5. Mejoras de Seguridad

### 5.1 Cloud Armor (WAF)

Agregar **Cloud Armor** como Web Application Firewall frente a Cloud Run:
- Proteccion contra DDoS
- Rate limiting global
- Reglas de IP allowlist/blocklist
- Proteccion OWASP Top 10

### 5.2 VPC Service Controls

Crear un perimetro de seguridad alrededor de los servicios GCP:
- Limitar exfiltracion de datos
- Controlar acceso a APIs desde dentro del perimetro
- Auditar intentos de acceso no autorizado

### 5.3 Audit Logging Completo

Habilitar **Data Access Audit Logs** para:
- Quien accedio a que documento
- Que preguntas se hicieron al agente
- Trazabilidad completa para compliance

---

## 6. Mejoras de Machine Learning

### 6.1 Fine-tuning del LLM

Usar los datos generados por `data_prep_tool` (JSONL) para hacer fine-tuning de Gemini:
- Dataset: preguntas frecuentes + respuestas validadas
- Plataforma: Vertex AI Model Tuning
- Mejora: respuestas mas especificas al dominio corporativo

### 6.2 Evaluacion Automatica del RAG (RAGAS)

Implementar evaluacion continua del pipeline RAG con **RAGAS**:

| Metrica | Que mide |
|---|---|
| **Faithfulness** | La respuesta es fiel a los chunks recuperados? |
| **Answer Relevancy** | La respuesta es relevante a la pregunta? |
| **Context Precision** | Los chunks recuperados son relevantes? |
| **Context Recall** | Se recuperaron todos los chunks necesarios? |

### 6.3 Embeddings Multimodales

Evolucionar de text-only a embeddings que soporten:
- Tablas dentro de PDFs
- Imagenes y diagramas (con modelos multimodales)
- Firmas y sellos (clasificacion)

---

## 7. Prioridad de Implementacion

### Fase 1 — Quick Wins (1-2 semanas)

| Mejora | Esfuerzo | Impacto |
|---|---|---|
| HyDE | Bajo | Alto — mejor relevancia |
| Streaming SSE | Medio | Alto — mejor UX |
| Feedback like/dislike | Bajo | Medio — datos para mejora |

### Fase 2 — Fundamentos (2-4 semanas)

| Mejora | Esfuerzo | Impacto |
|---|---|---|
| GitHub Actions CI/CD | Medio | Alto — automatizacion |
| Memoria persistente (Firestore) | Medio | Alto — historial de usuarios |
| Chunking semantico | Medio | Alto — mejor calidad RAG |
| Autenticacion (Firebase Auth) | Medio | Alto — seguridad |

### Fase 3 — Escalabilidad (1-2 meses)

| Mejora | Esfuerzo | Impacto |
|---|---|---|
| Vertex AI Vector Search | Alto | Alto — escalabilidad |
| Terraform IaC | Alto | Alto — reproducibilidad |
| Multi-Agent (LangGraph) | Alto | Alto — funcionalidad |
| Monitoreo completo | Medio | Alto — operabilidad |

### Fase 4 — Avanzado (2-3 meses)

| Mejora | Esfuerzo | Impacto |
|---|---|---|
| Fine-tuning Gemini | Alto | Alto — precision dominio |
| RAGAS evaluation | Medio | Alto — calidad medible |
| Re-ranking cross-encoder | Medio | Medio — precision |
| Cloud Armor + VPC Controls | Alto | Alto — seguridad enterprise |
| Upload de documentos | Alto | Alto — self-service |

---

## 8. Diagrama de Arquitectura v2.0 (Vision)

```
                                    ┌──────────────────┐
                                    │   Cloud Armor    │
                                    │   (WAF + DDoS)   │
                                    └────────┬─────────┘
                                             │
┌─────────────────────┐     HTTPS    ┌───────┴──────────────────────┐
│   Frontend (Vercel)  │ ───────────>│  Cloud Run Service v2        │
│   Next.js + Auth     │<───────────│  (FastAPI + LangGraph)        │
│                      │   SSE      │                               │
│ + Firebase Auth      │            │  Multi-Agent Orchestrator     │
│ + Feedback UI        │            │  ├── RAG Agent                │
│ + Source Cards       │            │  ├── Data Prep Agent          │
│ + Doc Upload         │            │  ├── Compliance Agent         │
└─────────────────────┘            │  └── Summary Agent            │
                                    │                               │
                                    │  Memoria: Firestore           │
                                    │  Auth: Firebase / IAP         │
                                    └──────┬────────────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    v                      v                      v
         ┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐
         │ Vertex AI        │   │ Cloud Storage    │   │ Firestore    │
         │ Vector Search    │   │ (GCS)            │   │              │
         │ (Managed Index)  │   │ PDFs + backups   │   │ Sesiones     │
         │                  │   │                  │   │ Feedback     │
         │ ANN search       │   │                  │   │ Analytics    │
         │ + Metadata       │   │                  │   │              │
         └──────────────────┘   └────────┬─────────┘   └──────────────┘
                                         │
                                         │
                              ┌──────────┴─────────────────┐
                              │  Cloud Run Job v2          │
                              │  + Cloud Tasks (cola)      │
                              │                            │
                              │  Document AI (OCR)         │
                              │  Chunking semantico        │
                              │  Embeddings multimodales   │
                              │  Re-ranking                │
                              │  RAGAS evaluation          │
                              └────────────────────────────┘

Observabilidad:
  Cloud Monitoring + Cloud Trace + Cloud Logging
  └── Grafana Dashboards + Alertas PagerDuty/Slack
```

---

## 9. Tecnologias Clave para el Roadmap

| Tecnologia | Uso | Servicio GCP |
|---|---|---|
| **LangGraph** | Multi-agent orchestration | - |
| **Vertex AI Vector Search** | Managed vector database | `aiplatform.googleapis.com` |
| **Firebase Auth** | Autenticacion de usuarios | `firebase.googleapis.com` |
| **Cloud Firestore** | Memoria persistente + analytics | `firestore.googleapis.com` |
| **Cloud Tasks** | Cola de procesamiento async | `cloudtasks.googleapis.com` |
| **Cloud Armor** | WAF + DDoS protection | `compute.googleapis.com` |
| **Terraform** | Infrastructure as Code | - |
| **GitHub Actions** | CI/CD | - |
| **RAGAS** | Evaluacion automatica de RAG | - |
| **Cloud Trace** | Distributed tracing | `cloudtrace.googleapis.com` |
