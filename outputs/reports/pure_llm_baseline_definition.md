# Pure LLM Baseline Definition

All variants are diagnostic/shadow-only.
- `raw_two_tools_current`: Current raw LLM with execute_sql and call_api, no extra scaffolding.
- `guided_two_tools_current`: Current guided prompt baseline with schema/API affordances.
- `structured_plan_then_tools`: LLM outputs a structured plan before tool use.
- `schema_retrieved_sql_agent`: Adds compact schema and endpoint retrieval context for LLM SQL planning.
- `validate_repair_sql_agent`: Adds SQLValidator/SQLGlot validation and up to two repair rounds.
- `evidence_locked_answer_agent`: Locks final answer claims to structured tool observations.
- `full_pure_llm_tool_agent_v1`: Combines planning, schema retrieval, SQL repair, API validation, and evidence-locked answer.
- `structured_sql_plan_agent_v1`: LLM emits structured SQL plan JSON; deterministic compiler emits validated SQL without repair.
- `structured_sql_plan_with_repair_v1`: Structured SQL plan JSON plus deterministic compiler and up to two plan repair rounds.
- `structured_sql_plan_backend_answer_only`: Structured SQL plan with deterministic tool-evidence answer fallback only.
- `structured_sql_plan_with_tool_choice_guard_v1`: Adds LLM evidence-source planning plus validator/retry before structured SQL/API tool use.
- `sql_first_when_validator_high_confidence_v1`: Runs SQL first when the tool-choice validator has high confidence local SQL is required.
- `api_only_only_when_sql_unavailable_v1`: Allows API-only planning only when local schema evidence is unavailable or live API is explicit.
