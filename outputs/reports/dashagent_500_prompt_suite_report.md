# DashAgent 500-Prompt Suite

- total_prompts: 500
- runtime_gold_separated: True
- diagnostic_internal_only: true

## Category Counts
- conceptual_no_tool: 60
- sql_only_local_snapshot: 120
- api_only_live_platform: 90
- sql_then_api_verification: 90
- mixed_conceptual_data: 40
- ambiguous_low_confidence: 40
- hard_stress: 60

## Stress Tags
- anti_hallucination_no_tool_conflict: 1
- anti_hallucination_unknown_capability: 1
- mixed_no_tool_block: 41
- low_low_safe_direct: 10
- low_low_safe_api_probe: 10
- post_sql_advisor_accept: 1
- post_sql_advisor_block: 1
- invalid_json_fallback: 1

## Example Runtime Prompts
- conceptual_no_tool: `da500_0001` What is a schema in Adobe Experience Platform? Use general terms for concept case 1.
- sql_only_local_snapshot: `da500_0061` How many schema records are in the local snapshot? SQL case 1.
- api_only_live_platform: `da500_0181` List current Adobe schema using the platform API. API case 1.
- sql_then_api_verification: `da500_0271` Use the local snapshot for schema, then call the live API only if the SQL answer is incomplete. SQL/API policy case 1.
- mixed_conceptual_data: `da500_0361` Explain what a merge policy is and list current merge policy objects if the live endpoint supports it. Mixed case 1.
- ambiguous_low_confidence: `da500_0401` Schemas, in plain language. Ambiguous case 1.
- hard_stress: `da500_0441` List schemas even though I first ask: what is a schema? Stress trigger 1.

Gold rows are stored only in the gold JSONL and are not present in runtime prompt rows.
