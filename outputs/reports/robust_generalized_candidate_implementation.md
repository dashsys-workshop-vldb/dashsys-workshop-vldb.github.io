# Robust Generalized Harness Candidate Implementation

- Candidate strategy implemented: `true`
- Candidate name: `ROBUST_GENERALIZED_HARNESS_CANDIDATE`
- Packaged default strategy: `SQL_FIRST_API_VERIFY`
- Packaged default changed: `false`
- Promotion judgment run: `false`

## Components
- `objective_features`: `true`
- `compact_json_llm_context`: `true`
- `semantic_decision`: `true`
- `anti_hallucination_feedback`: `true`
- `no_tool_verifier`: `true`
- `semantic_ladder`: `true`
- `safe_api_probe`: `true`
- `staged_evidence`: `true`
- `post_sql_deterministic_policy`: `true`
- `api_preservation_guard`: `true`
- `evidence_quality_classifier`: `true`
- `answer_slot_renderer`: `true`
- `evidence_grounded_answer_builder`: `true`
- `score_provenance_guard`: `true`
- `hardcode_fake_score_prevention`: `true`
- `runtime_leakage_guard`: `true`
- `real_agent_executor_path`: `true`
- `diagnostics_checkpoints`: `true`

## Disabled By Default
- `post_sql_llm_advisor`: `true`
- `broad_semantic_router_as_packaged_default`: `true`
- `simulated_trace`: `true`

## Strategy Selection
- `agent_executor`: `AgentExecutor(config).run(prompt, strategy="ROBUST_GENERALIZED_HARNESS_CANDIDATE")`
- `run_one_query`: `python3 scripts/run_one_query.py "What is a schema?" --strategy ROBUST_GENERALIZED_HARNESS_CANDIDATE --query-id robust_candidate_smoke`
- `run_dev_eval`: `python3 scripts/run_dev_eval.py --strict --strategies ROBUST_GENERALIZED_HARNESS_CANDIDATE`
- `internal_500_runner_mode`: `robust_generalized_harness_candidate_real`

## Tests Run
- `python3 -m pytest -q tests/test_robust_generalized_candidate.py`: 9 passed
- `python3 -m pytest -q tests/test_robust_generalized_candidate.py tests/test_real_behavior_applied_trials.py tests/test_staged_evidence_policy.py`: 32 passed
- `python3 scripts/run_one_query.py "What is a schema?" --strategy ROBUST_GENERALIZED_HARNESS_CANDIDATE --query-id robust_candidate_smoke`: passed; tool_call_count=0
- `python3 scripts/check_submission_ready.py`: ok=true; query_output_count=73; packaged strategy SQL_FIRST_API_VERIFY
- `git diff --check`: passed

## Known TODOs
- Run organizer 35 and internal 500 comparisons only in a later experiment pass.
- Stress the SAFE_API_PROBE path across all endpoint families with live/dry-run parity checks.
- Audit evidence-grounded answer builder quality row-by-row before considering any promotion.
- Keep LLM advisor excluded until a separate backend-cost and verifier-acceptance pass justifies it.
