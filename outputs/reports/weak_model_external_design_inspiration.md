# Weak Model External Design Inspiration

Diagnostic-only. The packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

The weak-model-lift work borrows lightweight concepts without importing large frameworks or using the packaged deterministic planner as a hidden oracle.

| Pattern | Implemented In | Why It Helps Weak Models | Robustness Guard |
| --- | --- | --- | --- |
| Vanna-style schema/context retrieval | `dashagent/nlp_generalization_layer.py`, `dashagent/weak_model_semantic_slots.py`, `dashagent/semantic_slot_compiler.py` | The weak model emits semantic slots rather than memorizing table names. | Slots map only to known schema tables/columns. |
| SQLCoder-style schema-aware SQL intent | `dashagent/weak_model_semantic_slots.py`, `dashagent/semantic_slot_compiler.py` | Semantic interpretation is converted into deterministic SQL. | Raw LLM SQL is not executed. |
| SQLFixAgent-style validation boundary | `dashagent/weak_model_slot_verifier.py`, `dashagent/semantic_slot_compiler.py` | Common tool-choice errors are caught before execution. | Local snapshot questions cannot remain API-only when SQL is required. |
| SQLGlot/SQLValidator-style safety | `dashagent/semantic_slot_compiler.py`, `dashagent/validators.py` | Weak-model mistakes cannot bypass SQL/API validation. | Only read-only validated SQL/API calls execute. |
| LangGraph/LangChain-style staged traces | `scripts/run_weak_model_lift_eval.py`, `scripts/run_weak_model_robustness_gate.py` | Lift is measurable by stage: slots, compile, execute, ground. | Reports are shadow-only and final submission format is unchanged. |
