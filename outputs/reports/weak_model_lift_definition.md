# Weak Model Lift Definition

Measure how much DashAgent scaffolding lifts weak-model correctness, tool validity, evidence grounding, robustness, and efficiency.

- Formula: `small_model_lift_score = DashAgent-assisted weak-model score - raw weak-model score`

## Modes

- `raw_weak_llm`
- `guided_weak_llm`
- `json_action_weak_llm`
- `semantic_slot_weak_llm`
- `weak_semantic_slots_only`
- `slot_to_sql_compiled_agent`
- `weak_slots_to_sql_compiler`
- `weak_slots_to_sql_api_compiler`
- `evidence_guarded_weak_agent`
- `weak_full_dashagent_scaffold`
- `weak_scaffold_balanced_sql_api_v1`
- `weak_scaffold_api_recovery_v1`
- `weak_scaffold_answer_grounded_v1`
- `weak_scaffold_balanced_full_v1`
- `weak_scaffold_sql_retrieval_v1`
- `weak_scaffold_sql_unit_tested_v1`
- `weak_scaffold_sql_retrieval_repair_v1`
- `weak_scaffold_balanced_sql_api_v2`
- `full_dashagent_current`
