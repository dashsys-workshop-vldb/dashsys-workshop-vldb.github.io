# Semantic Route Decision Ladder Trial

Classification: `diagnostic_only`.

The semantic routing harness ran in shadow-only deterministic fallback mode. It did not change packaged routing, planning, SQL/API execution, answer synthesis, final submission artifacts, or Adobe API behavior.

## Summary

- total_prompts: `98`
- llm_direct_candidates: `5`
- llm_safe_direct_candidates: `0`
- safe_api_probe_candidates: `1`
- evidence_pipeline_candidates: `92`
- no_tool_allowed_count: `5`
- no_tool_blocked_count: `93`
- false_no_tool_risk_count: `0`
- conceptual_false_positive_tool_routes_reduced: `5`
- estimated_tool_call_savings: `6`
- average_context_token_cost: `233.52`
- average_tier_used: `0.01`
- low_low_case_count: `1`
- routing_gate_initial_pass_count: `98`
- routing_gate_initial_fail_count: `0`
- routing_gate_revision_attempt_count: `0`
- routing_gate_revision_success_count: `0`
- routing_gate_revision_fail_count: `0`
- routing_gate_extra_token_estimate: `0`
- recommendation: `keep_shadow_only`

## Action Distribution

- `EVIDENCE_PIPELINE`: `92`
- `LLM_DIRECT`: `5`
- `SAFE_API_PROBE`: `1`

## Prompt Rows

| prompt_id | source | current route | shadow action | no-tool allowed | false no-tool risk |
|---|---|---:|---:|---:|---:|
| `public_001` | `public_dev` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_002` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_003` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_004` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_005` | `public_dev` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_006` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_007` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_008` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_009` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_010` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_011` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_012` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_013` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_014` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_015` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_016` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_017` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_018` | `public_dev` | `API_ONLY` | `SAFE_API_PROBE` | `False` | `False` |
| `public_019` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_020` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_021` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_022` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_023` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_024` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_025` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_026` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_027` | `public_dev` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_028` | `public_dev` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_029` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_030` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_031` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_032` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_033` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_034` | `public_dev` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `public_035` | `public_dev` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0001` | `generated` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0002` | `generated` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0003` | `generated` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0004` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0005` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0006` | `generated` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0007` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0008` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0009` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0010` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0011` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0012` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0013` | `generated` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0014` | `generated` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0015` | `generated` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0016` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0017` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0018` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0019` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0020` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0021` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0022` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0023` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0024` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0025` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0026` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0027` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0028` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0029` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0030` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0031` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0032` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0033` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0034` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0035` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0036` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0037` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0038` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0039` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0040` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0041` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0042` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0043` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0044` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0045` | `generated` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0046` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0047` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0048` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0049` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `gen_0050` | `generated` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `conceptual_001` | `conceptual_keyword` | `LOCAL_DB_ONLY` | `LLM_DIRECT` | `True` | `False` |
| `conceptual_002` | `conceptual_keyword` | `API_ONLY` | `LLM_DIRECT` | `True` | `False` |
| `conceptual_003` | `conceptual_keyword` | `LOCAL_DB_ONLY` | `LLM_DIRECT` | `True` | `False` |
| `conceptual_004` | `conceptual_keyword` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `conceptual_005` | `conceptual_keyword` | `LOCAL_DB_ONLY` | `LLM_DIRECT` | `True` | `False` |
| `conceptual_006` | `conceptual_keyword` | `LOCAL_DB_ONLY` | `LLM_DIRECT` | `True` | `False` |
| `data_001` | `concrete_data` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `data_002` | `concrete_data` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `data_003` | `concrete_data` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `data_004` | `concrete_data` | `LOCAL_DB_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `data_005` | `concrete_data` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `mixed_001` | `mixed` | `API_ONLY` | `EVIDENCE_PIPELINE` | `False` | `False` |
| `mixed_002` | `mixed` | `SQL_PLUS_API` | `EVIDENCE_PIPELINE` | `False` | `False` |
