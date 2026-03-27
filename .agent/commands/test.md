Ejecuta los tests del agente para validar las 3 herramientas:

```bash
python test_agent.py
```

Verifica que los 3 tests pasen:
1. `data_prep_tool` — Limpieza HTML → JSONL
2. `rag_search_tool` — Búsqueda RAG en PDFs corporativos
3. `dlp_anonymizer_tool` — Anonimización de PII

Si hay errores, revisa:
- Que `GOOGLE_API_KEY` esté en `.env`
- Que los PDFs estén descargados en `docs/corporativos/`
- Que las dependencias estén instaladas (`pip install -r requirements.txt`)
