# V2 Final Benchmark Summary

## Purpose
This benchmark evaluates finalized V2 stability and objective correctness. It does not promote V2.

## Architecture Reminder
- LLM owns route, decomposition, SQL/API candidate generation, final answer composition, and repair.
- Backend owns scheduling, gates, execution, storage, error checks, and objective diagnostics only.
- Packaged default remains `SQL_FIRST_API_VERIFY`.

## Commands Run
- `git status --short`
- `python3 -m pytest -q`
- `python3 scripts/check_submission_ready.py`
- `python3 scripts/generate_sdk_usage_audit.py`
- `git diff --check`
- `rg -n "run_dev_eval|Organizer35|Internal50|promotion|hidden_style|integrated_robustness|500_prompt|strict|score|gate" scripts tests README.md docs . || true`
- `ls scripts`
- `python3 scripts/run_dev_eval.py --help`
- `python3 scripts/run_dashagent_500_prompt_suite_eval.py --help`
- `python3 scripts/run_dev_eval.py --strict --strategies SQL_FIRST_API_VERIFY`
- `python3 scripts/run_dev_eval.py --strict --strategies ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`
- `python3 scripts/run_dashagent_500_prompt_suite_eval.py --engine real_agent --mode packaged_baseline_real --limit 50 --seed 20260525 --clean --output-dir outputs/reports/v2_final_benchmark/internal50/packaged_baseline/outputs --report-dir outputs/reports/v2_final_benchmark/internal50/packaged_baseline`
- `python3 scripts/run_dashagent_500_prompt_suite_eval.py --engine real_agent --mode robust_generalized_harness_candidate_v2_real --limit 50 --seed 20260525 --clean --output-dir outputs/reports/v2_final_benchmark/internal50/v2/outputs --report-dir outputs/reports/v2_final_benchmark/internal50/v2`
- `python3 scripts/run_semantic_route_promotion_gate.py`
- `python3 scripts/run_integrated_robustness_gate.py`
- `python3 scripts/run_hidden_style_eval.py`
- `python3 scripts/check_submission_ready.py`
- `python3 scripts/run_one_query.py <7 focused prompts> --strategy ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`

## Preflight Results
| Check | Result |
| --- | --- |
| pytest | 991 passed, 1 skipped |
| check_submission_ready | ok=True; default_sql_first=True; secret_scan_ok=True |
| SDK usage audit | runtime_llm_direct_http_hits=0 |
| git diff --check | passed |
| .env.local | git-ignored, not tracked, not printed |

## Baseline Default Results
| Metric | SQL_FIRST_API_VERIFY |
| --- | --- |
| completed | True |
| query output count | 35 |
| SQL calls | 15 |
| API calls | 36 |
| tool calls | 51 |
| error_count | 0 |
| validation_failures | 1 |
| unsupported_claims | not emitted by strict script; Internal50 baseline summary did not expose a nonzero count |
| raw avg_final_score | 0.6563 |
| raw avg_correctness_score | 0.6812 |
| raw avg_answer_score | 0.3223 |
| raw avg_sql_score | 0.9333 |
| raw avg_api_score | 0.9791 |

## V2 Results
| Metric | ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 |
| --- | --- |
| completed | True |
| query output count | 35 |
| LLM planner calls | 35 |
| planner usable plan/pass success count | 0 |
| total declared passes | 0 |
| multi-pass rows | 0 |
| exact-pass cache hits | 0 |
| SQL calls | 0 |
| API calls | 0 |
| tool calls | 0 |
| SQL gate pass/fail | 0/0 |
| API gate pass/fail | 0/0 |
| SQL/API repair attempts | 0/0 |
| EvidenceBus built count | 35 |
| ResultBundle built count | 35 |
| final syntax gate counts | {"failed:missing_final_answer": 35} |
| final semantic gate counts | {"failed:syntax_gate_failed": 35} |
| provider/model error rows | 35 |
| missing SQL when gold SQL exists | 15 |
| missing API when gold API exists | 31 |
| raw avg_final_score | 0.0606 |
| raw avg_correctness_score | 0.0745 |
| raw avg_answer_score | 0.1775 |
| raw avg_sql_score | 0.0 |
| raw avg_api_score | 0.0 |

### V2 Provider/Planner Error Counts
- 35 planner rows: `Error code: 404 - {'detail': "Model 'Gpt 4o' is not a recognised model id. Browse available base models with `GET /v1/models` or in the docs at https://docs.pioneer.ai/api-reference. To call a fine-tuned model, pass its training-job UUID."}`
- 35 final composer rows: `Error code: 404 - {'detail': "Model 'Gpt 4o' is not a recognised model id. Browse available base models with `GET /v1/models` or in the docs at https://docs.pioneer.ai/api-reference. To call a fine-tuned model, pass its training-job UUID."}`

## Internal50 Focused Subset Results
| Metric | packaged_baseline_real | robust_generalized_harness_candidate_v2_real |
| --- | --- | --- |
| completed | True | True |
| prompt_count | 50 | 50 |
| combined_diagnostic_score raw | 0.7168 | 0.3785 |
| behavior_score raw | 0.8238 | 0.52 |
| final_answer_correctness raw | 0.6525 | 0.52 |
| SQL calls | 40 | 0 |
| API calls | 33 | 0 |
| no_tool_false_positive | 0 | 46 |
| api_required_underuse | 0 | 0 |
| unsupported_claims | 0 | 0 |
| tool_underuse | 6 | 46 |
| route_accuracy raw | 0.8 | 0.08 |

## Gate Results
| Gate | Result |
| --- | --- |
| semantic route promotion gate | promotion_allowed=False; recommendation=keep_shadow_only; public_dev_strict_no_regression=False |
| integrated robustness gate | promotion_allowed=False; recommendation=blocked_by_robustness_regression |
| hidden style eval | passed=48/48; failed=0 |
| check_submission_ready | ok=True; default unchanged=True |

## Focused Smoke Results
| Prompt | Route | SQL | API | Bypass | EvidenceBus | Syntax gate | Semantic gate | Expected? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| When was the journey "Birthday Message" published? | EVIDENCE_PIPELINE | 0 | 0 | False | True | False | False | False |
| Compare local and live status of Birthday Message if both are available. | EVIDENCE_PIPELINE | 0 | 0 | False | True | False | False | False |
| What is a schema? | EVIDENCE_PIPELINE | 0 | 0 | False | True | False | False | False |
| How many schema records are in the local snapshot? | EVIDENCE_PIPELINE | 0 | 0 | False | True | False | False | False |
| In the phrase "list schemas", what does "list" mean? | EVIDENCE_PIPELINE | 0 | 0 | False | True | False | False | False |
| Explain what inactive journey means and show inactive journeys. | EVIDENCE_PIPELINE | 0 | 0 | False | True | False | False | False |
| What schemas do I have? | EVIDENCE_PIPELINE | 0 | 0 | False | True | False | False | False |

## Failure Analysis
Primary objective failure: the V2 LLM provider/model calls failed, so the planner produced no usable SQL/API pass graph and the final composer returned no valid final answer. V2 then failed closed into `EVIDENCE_PIPELINE` with zero declared passes, zero SQL/API tool calls, empty EvidenceBus/ResultBundle, failed final syntax/semantic gates, and missing required information for data prompts.

| Objective error type | Count / finding |
| --- | --- |
| provider_error | 35 |
| planner_toolcall_failure_or_no_usable_plan | 35 |
| pass_graph_failure | 0 |
| sql_gate_failure | 0 |
| api_gate_failure | 0 |
| execution_error | 0 |
| evidence_bus_missing_evidence | 35 |
| final_syntax_gate_failure | 35 |
| final_semantic_grounding_failure | 35 |
| unsupported_claim | 0 |
| missing_required_info | 46 |
| scope_confusion | not detected, but not assessable for V2 rows because no SQL/API evidence was produced |
| timeout | 0 |

## Correctness Notes
- This report does not treat hidden/gold wording closeness as the correctness standard.
- Objective V2 correctness failed because required evidence was not acquired for data/mixed prompts.
- Unsupported claims remained 0 in Internal50, but this is because V2 returned conservative fallback answers with no evidence, not because it answered data prompts correctly.
- API_ERROR/LIVE_EMPTY/local-live scope handling could not be meaningfully assessed for V2 benchmark rows because no SQL/API evidence was produced.

## Keep / Commit / Promote Recommendation
| Decision | Value | Reason |
| --- | --- | --- |
| Safe to keep | yes | Benchmark/report artifacts are diagnostic; packaged default unchanged. |
| Safe to commit reports | yes | Reports reflect objective failures and no secrets were printed. |
| Safe to promote V2 | no | Promotion gate blocks; V2 evidence path produced zero tools and Internal50 no_tool_false_positive=46. |

