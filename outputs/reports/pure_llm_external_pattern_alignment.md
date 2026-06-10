# Pure LLM External Pattern Alignment

Diagnostic-only comparison; no external framework is imported.
- `LangChain-style controlled agent workflow`: implemented `True` in `dashagent/pure_llm_tool_agent.py`; guard: explicit plan, validated tool steps, trace report; no packaged runtime promotion
- `Vanna-style schema retrieval/context`: implemented `True` in `dashagent/llm_sql_context_builder.py`; guard: known SchemaIndex tables/columns only; no gold answers or query IDs
- `SQLCoder-style schema-aware SQL prompt`: implemented `True` in `dashagent/llm_tool_agent_prompts.py`; guard: JSON-only candidate schema and existing SQLValidator/SQLGlot validation
- `SQLFixAgent-style validation/repair loop`: implemented `True` in `dashagent/llm_sql_repair_loop.py`; guard: invalid SQL is never executed; max two repair rounds
- `SQLGlot/SQLValidator hard validation`: implemented `True` in `dashagent/validators.py`; guard: read-only, known table/column, AST destructive SQL checks before execution
