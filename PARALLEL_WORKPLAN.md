# Parallel DASHSys 0.75 Score-Push Workplan

## Baseline
- Baseline branch: `main`
- Baseline commit SHA: `b583624c1977d7bf7a4403ba3a77779f602d2f79`
- Baseline strict final score: `0.6491`
- Baseline correctness: `0.6743`
- Baseline estimated tokens/runtime/tools: `831.4571 / 0.0115 / 1.4571`
- Baseline hidden-style eval: `48/48`
- Preferred strategy: `SQL_FIRST_API_VERIFY`
- Required success target: `strict_final_score >= 0.7500`

All worker branches were created from the same baseline commit above. Workers may produce candidates, feature flags, isolated evals, and reports only. Only `codex/score075-integration` may merge branches or run a packaged trial.

## Global Safety Rules
- Do not change scorer logic, strict eval logic, hidden-style expectations, or final submission format.
- Do not write to `outputs/final_submission/`, official `outputs/eval/`, or packaged query-output folders from worker branches.
- Do not disable official-token reduction.
- Do not enable compact context.
- Do not enable repair execution unless a separate strict packaged trial proves it safe.
- Do not use gold SQL/API paths, gold answers, query IDs, exact public query strings, or memorized final answers for runtime behavior.
- If a needed edit is outside a worker's allowed files, write `outputs/score075_<area>_handoff.md` instead of editing it.
- Every worker must declare dependencies. A branch with an unmerged dependency is blocked until integration merges that dependency.

## Workers

| Branch | Scope | Dependencies | Allowed files | Isolated outputs |
|---|---|---|---|---|
| `codex/score075-coordinator-baseline` | Baseline snapshots, workplan, status table, research notes, shared gate definitions | none | `PARALLEL_WORKPLAN.md`, `scripts/generate_improvement_backlog.py`, `scripts/autonomous_improvement_loop.py`, `scripts/generate_autonomous_score_push_report.py`, report-only helpers | `outputs/score075_baseline_report.*`, `outputs/autonomous_research_notes.*`, `outputs/score075_parallel_status.*` |
| `codex/score075-dryrun-answer` | Evidence-aware dry-run answer candidates from recorded evidence only | local-index for evidence object integration | `dashagent/answer_templates.py`, `dashagent/answer_synthesizer.py`, dry-run answer helper/tests only | `outputs/score075_dryrun_answer_eval.*` |
| `codex/score075-local-index` | Parquet-derived evidence-object local index, no final-answer cache | robustness-leakage for provenance tests | `dashagent/local_knowledge_index.py`, `scripts/build_local_knowledge_index.py`, `scripts/run_local_index_candidate_eval.py`, local-index tests | `outputs/local_knowledge_index_report.*`, `outputs/local_index_candidate_eval.*` |
| `codex/score075-endpoint-routing` | Leakage-safe endpoint/schema routing candidates | robustness-leakage | `dashagent/endpoint_schema_rule_candidates.py`, endpoint routing candidate scripts/tests only | `outputs/score075_endpoint_routing_eval.*` |
| `codex/score075-candidate-generation` | Deterministic candidate families and isolated candidate reports | local-index, endpoint-routing, answer-shape | `dashagent/targeted_candidate_generator.py`, candidate-generation scripts/tests only | `outputs/score075_candidate_generation_eval.*` |
| `codex/score075-execution-selector` | Execution-guided selector and safety gates | candidate-generation, robustness-leakage | `dashagent/execution_based_candidate_selector.py`, `scripts/run_execution_candidate_search.py`, selector tests | `outputs/execution_candidate_search.*`, `outputs/execution_candidate_search/` |
| `codex/score075-llm-search` | Optional LLM candidate search, skipped if no key | candidate-generation, execution-selector | `dashagent/llm_candidate_generator.py`, `scripts/run_llm_candidate_search.py`, LLM-search tests | `outputs/llm_candidate_search.*` |
| `codex/score075-answer-shape` | Count/list/detail/status/date answer-shape normalization candidates | robustness-leakage | answer-shape helpers/tests only; no scorer edits | `outputs/score075_answer_shape_eval.*` |
| `codex/score075-robustness-leakage` | Leakage, hidden-style, evidence-boundary, and candidate-diversity tests | none | tests and report-only robustness scripts only | `outputs/score075_robustness_report.*` |
| `codex/score075-integration` | Pairwise merge validation, packaged trial, diff report, readiness/research updates | all accepted branches | integration scripts, report integrations, packaging exclusions only | `outputs/autonomous_packaged_trial.*`, `outputs/autonomous_score_push_report.*`, `outputs/score075_integration_diff_report.*` |

## Merge Order
1. `codex/score075-robustness-leakage`
2. `codex/score075-local-index`
3. `codex/score075-dryrun-answer`
4. `codex/score075-answer-shape`
5. `codex/score075-endpoint-routing`
6. `codex/score075-candidate-generation`
7. `codex/score075-execution-selector`
8. `codex/score075-llm-search`
9. Packaged trial changes from `codex/score075-integration`
10. Reports/readiness integration

## Pairwise Merge Validation
After each branch merge, integration must run:

```bash
python3 -m pytest <targeted tests for branch>
python3 scripts/run_hidden_style_eval.py
python3 scripts/run_dev_eval.py --strict
```

If behavior or submission packaging changed, also run:

```bash
python3 scripts/package_submission.py
python3 scripts/package_query_outputs.py
python3 scripts/check_submission_ready.py
```

If two individually passing branches fail together, integration must identify the conflict and revert the lower-value branch.

## Final Validation
```bash
python3 -m pytest
python3 scripts/build_local_knowledge_index.py
python3 scripts/run_local_index_candidate_eval.py
python3 scripts/generate_improvement_backlog.py
python3 scripts/run_execution_candidate_search.py
python3 scripts/run_llm_candidate_search.py
python3 scripts/run_autonomous_packaged_trial.py
python3 scripts/generate_autonomous_score_push_report.py
python3 scripts/run_hidden_style_eval.py
python3 scripts/generate_accuracy_promotion_decision_report.py
python3 scripts/generate_winner_readiness_report.py
python3 scripts/generate_research_inspired_report.py
python3 scripts/run_dev_eval.py --strict
python3 scripts/package_submission.py
python3 scripts/package_query_outputs.py
python3 scripts/check_submission_ready.py
```

## Promotion Gates
Integration keeps a merged change only if:
- `strict_final_score` improves; hard success requires `>= 0.7500`.
- `correctness >= 0.6743`.
- Hidden-style remains `48/48`.
- Tokens `<= 831.4571 * 1.02`.
- Runtime `<= 0.0115 * 1.10`.
- Tool calls `<= 1.4571`, unless score is `>= 0.7500` and justified.
- `no_secret_scan.ok=true`.
- Final submission format is unchanged.
- Preferred strategy remains `SQL_FIRST_API_VERIFY`.
- Official-token reduction remains enabled.
- Compact context remains disabled.
- Repair execution remains disabled unless separately proven safe.
- No unsafe or gold-derived runtime behavior is introduced.

## Pre-Existing Integration Blocker
The baseline workspace currently contains untracked duplicate `outputs/final_submission/* 2.*` artifacts. Workers must not touch final submission directly. Integration must clean or quarantine these only through existing safe cleanup/package-readiness paths before final submission validation.
