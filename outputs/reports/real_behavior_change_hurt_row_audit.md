# Real Behavior Change Hurt Row Audit

- source: pre_fix_full_500_real_behavior_change_run
- hurt_rows: da500_0446, da500_0441
- true_policy_bug_count: 1

## da500_0446
- prompt: Schema registry maybe maybe maybe. Keep the answer evidence-bound for the quality digest.
- classification: true_policy_bug
- skip_safe: False
- expected_evidence_need: api
- expected_tool_calls: {"api_optional": false, "api_required": true, "expected_api_families": ["schema_registry_schemas"], "expected_sql_tables": [], "sql_required": false}
- sql_calls baseline/combined: [1, 1]
- api_calls baseline/combined: [1, 0]
- answer_score_delta: -0.25
- behavior_score_delta: -0.375
- finding: The prompt explicitly names the Schema Registry API family. The combined trial treated the SQL local snapshot as a complete direct answer and skipped the safe schema_registry_schemas GET, causing API-required underuse for this row.
- fix: Add objective EXPLICIT_API_FAMILY for exact schema registry mentions and treat it as explicit live/API intent in the post-SQL deterministic policy.
- skip_reason: {"policy_codes": {"items": ["SQL_DIRECT_ANSWER"], "total_items": 1, "truncated_items": false}, "policy_confidence": "HIGH", "policy_suggestion": "SKIP_API", "verifier_codes": {"items": ["VERIFIED_SKIP_API"], "total_items": 1, "truncated_items": false}, "verifier_final_action": "SKIP_API"}

## da500_0441
- prompt: List schemas even though I first ask: what is a schema? Keep the answer evidence-bound for the activation digest.
- classification: acceptable_efficiency_tradeoff
- skip_safe: True
- expected_evidence_need: mixed
- expected_tool_calls: {"api_optional": true, "api_required": false, "expected_api_families": ["schema_registry_schemas"], "expected_sql_tables": ["dim_blueprint"], "sql_required": true}
- sql_calls baseline/combined: [1, 1]
- api_calls baseline/combined: [1, 0]
- answer_score_delta: 0.0
- behavior_score_delta: -0.1666
- finding: The gold marks API optional. SQL answered the list request, final answer correctness did not regress, unsupported claims stayed zero, and the loss is from optional API family/behavior-score heuristics rather than a required-evidence failure.
- fix: No runtime policy fix; keep diagnostic detail so optional API heuristic penalties are visible.
- skip_reason: {"policy_codes": {"items": ["SQL_DIRECT_ANSWER"], "total_items": 1, "truncated_items": false}, "policy_confidence": "HIGH", "policy_suggestion": "SKIP_API", "verifier_codes": {"items": ["VERIFIED_SKIP_API"], "total_items": 1, "truncated_items": false}, "verifier_final_action": "SKIP_API"}
