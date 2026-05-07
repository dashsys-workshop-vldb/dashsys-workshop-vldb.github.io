# Score 0.75 Integration Diff Report

- Current branch: `codex/score075-integration`
- Current commit: `e9882992`
- Merged branches: 6
- Rejected branches: 3
- Strict score before/after/delta: 0.6491 / 0.6491 / 0.0
- Correctness before/after/delta: 0.6743 / 0.6743 / 0.0
- Tokens/runtime/tools delta: 0.0 / -0.0002 / 0.0
- Hidden-style: `48/48`
- Pytest: `266 passed`
- Readiness/no-secret: `True` / `True`
- 0.75 reached: `False`
- Final recommendation: `submit_current_official_token_reduction_version`

## Branch Decisions

| Branch | Decision | Reason | Score Delta | Hidden | Tests |
|---|---|---|---:|---|---|
| `codex/score075-coordinator-baseline` | `rejected` | not merged; report-only branch overlapped current integration artifacts and produced no score-bearing change | 0.0 | 0/48 | - |
| `codex/score075-robustness-leakage` | `merged` | required guard infrastructure; targeted/full tests pass with no strict regression | 0.0 | 0/48 | python3 -m pytest tests/test_score075_robustness_leakage.py -q<br>python3 -m pytest -q<br>python3 scripts/run_hidden_style_eval.py<br>python3 scripts/run_dev_eval.py --strict |
| `codex/score075-local-index` | `merged` | dependency infrastructure for candidate generation; no packaged-path regression | 0.0 | 0/48 | python3 -m pytest tests/test_local_knowledge_index.py -q<br>python3 scripts/run_hidden_style_eval.py<br>python3 scripts/run_dev_eval.py --strict |
| `codex/score075-dryrun-answer` | `rejected` | merged then reverted: behavior-changing branch tied strict score and is not required by a proven score-improving branch | 0.0 | 0/48 | python3 -m pytest tests/test_answer_correctness_layer.py -q<br>python3 scripts/run_hidden_style_eval.py<br>python3 scripts/run_dev_eval.py --strict |
| `codex/score075-answer-shape` | `merged` | dependency infrastructure for candidate generation; no packaged-path regression | 0.0 | 0/48 | python3 -m pytest tests/test_answer_shape_optimization.py -q<br>python3 scripts/run_hidden_style_eval.py<br>python3 scripts/run_dev_eval.py --strict |
| `codex/score075-endpoint-routing` | `merged` | shadow infrastructure; no packaged-path regression and no promotion claim | 0.0 | 0/48 | python3 -m pytest tests/test_endpoint_schema_rule_candidates.py -q<br>python3 scripts/run_hidden_style_eval.py<br>python3 scripts/run_dev_eval.py --strict |
| `codex/score075-candidate-generation` | `merged` | dependency infrastructure for execution selector; no packaged-path regression | 0.0 | 0/48 | python3 -m pytest tests/test_score075_candidate_generation.py -q<br>python3 scripts/run_hidden_style_eval.py<br>python3 scripts/run_dev_eval.py --strict |
| `codex/score075-execution-selector` | `merged` | shadow infrastructure; no packaged-path regression; no selected safe score-improving candidate | 0.0 | 0/48 | python3 -m pytest tests/test_execution_based_candidate_selector.py tests/test_score_push_pipeline.py::test_execution_candidate_search_isolated_and_shadow_only -q<br>python3 scripts/run_hidden_style_eval.py<br>python3 scripts/run_dev_eval.py --strict |
| `codex/score075-llm-search` | `rejected` | merged then reverted: latest OpenRouter run produced zero candidates; no safe score-improving candidate available | 0.0 | 0/48 | python3 -m pytest tests/test_llm_client.py tests/test_llm_candidate_search.py tests/test_score_push_pipeline.py::test_llm_candidate_search_skips_without_keys -q |

## Notes

- No branch achieved a strict score improvement over 0.6491.
- No success is claimed because strict_final_score is below 0.7500.
- Behavior-changing dry-run answer and optional LLM-search branches were rejected/reverted.
- Accepted branches are retained only on the integration branch as shadow/default-off infrastructure; current main submit-ready version is preserved.
