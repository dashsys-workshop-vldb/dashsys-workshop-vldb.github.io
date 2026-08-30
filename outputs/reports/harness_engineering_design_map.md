# Harness Engineering Design Map

Shadow-only mapping of external harness patterns to DashAgent weak-model modules.

| Pattern | Module | Gap | Correctness | Efficiency | Risk |
| --- | --- | --- | --- | --- | --- |
| Vanna-style retrieval | `dashagent/weak_sql_schema_retriever.py` | Improve ranking confidence and value sampling. | medium | low | robustness `low`, generalization `low` |
| SQLCoder-style prompt structure | `dashagent/weak_model_output_schemas.py` | Use schemas for hosted weak-model calls. | medium | neutral | robustness `low`, generalization `low` |
| CHESS-style SQL unit testing | `dashagent/weak_sql_unit_tester.py` | Broaden unit tests for group-by and relationship cases. | medium | low | robustness `low`, generalization `low` |
| DIN-SQL/DEA-SQL | `dashagent/semantic_slot_compiler.py` | Add stronger decomposition traces. | medium | neutral | robustness `low`, generalization `low` |
| SQLFixAgent | `dashagent/weak_sql_repair_loop.py` | Integrate hosted weak-model retry when available. | medium | low | robustness `medium`, generalization `low` |
| Guardrails/Instructor/Outlines | `dashagent/weak_model_output_schemas.py` | Use strict schemas in all weak-model calls. | medium | low | robustness `low`, generalization `low` |
| TraceSafe/PROMPTEVALS | `dashagent/weak_model_harness_assertions.py` | Feed assertion failures back into repair loops. | medium | low | robustness `low`, generalization `low` |
