---
name: rag-search
description: |
  Workflow para búsqueda RAG (Retrieval-Augmented Generation) sobre
  documentos corporativos PDF. Fragmenta PDFs, calcula relevancia por
  scoring, y retorna contexto para el LLM. Usar cuando se trabaje con
  búsquedas semánticas o procesamiento de documentos PDF.
---

## Use this skill when

- Implementando búsqueda RAG sobre PDFs corporativos
- Fragmentando documentos PDF para indexación
- Calculando relevancia/scoring de fragmentos
- Integrando contexto de documentos en respuestas del agente

## Do not use this skill when

- Descargando PDFs de Drive (usar `drive-loader` en su lugar)
- Anonimizando datos PII (usar `dlp_anonymizer_tool`)
- Limpiando HTML (usar `data_prep_tool`)

## Instructions

### Flujo RAG

1. **Cargar PDFs** desde `docs/corporativos/` (subdirectorios por categoría)
2. **Fragmentar** cada PDF en chunks de texto con metadata (archivo, página, categoría)
3. **Buscar** fragmentos relevantes usando scoring por palabras clave
4. **Retornar** los top-K resultados con relevancia y contexto

### Estructura de documentos

```
docs/corporativos/
├── POLITICAS/         # Políticas corporativas
├── PROCEDIMIENTOS/    # Procedimientos operativos
├── REGLAMENTOS/       # Reglamentos internos
└── OTROS/             # Documentos sin clasificar
```

### Scoring de relevancia

- Coincidencia exacta de término → mayor puntaje
- Coincidencia en título/nombre de archivo → bonus
- Categoría del documento → metadata enriquecida
- Ordenar por score descendente, retornar top resultados

## Safety

- No exponer contenido completo de documentos confidenciales
- Limitar tamaño de respuesta para no exceder contexto del LLM
- Validar que los PDFs sean legibles antes de fragmentar
