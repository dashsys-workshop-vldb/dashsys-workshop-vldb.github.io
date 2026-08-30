# V2 Routing Boundary Ablation Report

## Executive Summary

The current ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 routing-boundary patch is safe to keep and safe to commit as a research/shadow improvement, but it is not safe to promote over SQL_FIRST_API_VERIFY.

The boundary behavior works as intended:

- Pure high-confidence concept/meta prompts bypass SQL, API, EvidenceBus, AnswerSlots, BroadQuestionClassifier, AnswerIntentRouter, and HybridMixedAnswerComposer.
- Mixed, ambiguous-data-like, count, status/date/entity, user-specific, and evidence-like prompts still enter the evidence-grounded path.
- SQL_FIRST_API_VERIFY remains the packaged default.
- Local tests pass: 888 passed, 1 skipped.
- check_submission_ready passes.
- Hidden-style eval passes 48/48.
- Internal50 improves the diagnostic combined score and reduces SQL/API calls.
- Organizer35 still trails SQL_FIRST_API_VERIFY on final/correctness/answer/API, so this should remain shadow-only.

Final recommendation: safe to keep, safe to commit, keep shadow-only, not safe to promote.

## Code / Diff Summary

Working directory:

```text
/Users/tanqinyang/Desktop/dashsys-workshop-vldb
```

The routing-boundary source patch is already committed in HEAD history:

```text
8041728ef1 Bypass evidence bus for safe direct conceptual prompts
28c9aa804a Tighten pre-evidence routing boundary for direct LLM prompts
```

The expected routing-boundary source files are present in the committed patch, not as uncommitted source changes:

```text
dashagent/executor.py
dashagent/pre_evidence_routing_boundary.py
dashagent/progressive_evidence_policy.py
dashagent/prompt_semantic_ir.py
tests/test_robust_generalized_candidate.py
```

Current uncommitted changes after this evaluation pass are generated output/report files under `outputs/`, not source-code changes. `git diff --check` passed.

Generated output changes observed after the requested runs include:

```text
outputs/hidden_style_eval.json
outputs/reports/hardcoded_runtime_and_score_path_audit.json
outputs/reports/hardcoded_runtime_and_score_path_audit.md
outputs/reports/integrated_robustness_gate.json
outputs/reports/integrated_robustness_gate.md
outputs/reports/semantic_route_promotion_gate.json
outputs/visualizations/*
```

This report was saved as:

```text
outputs/reports/v2_routing_boundary_ablation_report_for_senior.md
```

## Test Commands Run

Repository state and diff checks:

```bash
pwd
git status --short
git diff --stat
git diff --check
```

Local correctness checks:

```bash
python3 -m pytest -q
python3 scripts/check_submission_ready.py
git diff --check
```

Benchmark/gate discovery:

```bash
rg -n "Organizer35|Internal50|promotion|gate|benchmark|strict|strategies|run_dev_eval|run_semantic_route_promotion_gate|run_integrated_robustness_gate|hidden_style|500_prompt|score|tool_calls|unsupported_claims" scripts tests README.md docs . || true
ls scripts
find outputs -maxdepth 3 -type f | sort | tail -120
```

Boundary trace checks were run through `AgentExecutor` with strategy `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2`.

Organizer35 strict comparison:

```bash
python3 scripts/run_dev_eval.py --help || true
DASHAGENT_OUTPUTS_DIR=/tmp/v2_org35_eval python3 scripts/run_dev_eval.py --strict --allow-live-diagnostic-without-success --strategies SQL_FIRST_API_VERIFY,ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2
```

Internal50 focused subset:

```bash
python3 scripts/run_dashagent_500_prompt_suite_eval.py --help || true
python3 scripts/run_dashagent_500_prompt_suite_eval.py \
  --engine real_agent \
  --suite data/benchmarks/dashagent_500_prompt_suite.jsonl \
  --gold data/benchmarks/dashagent_500_prompt_suite_gold.jsonl \
  --mode packaged_baseline_real \
  --mode robust_generalized_harness_candidate_v2_real \
  --limit 50 \
  --seed 20260525 \
  --clean \
  --output-dir /tmp/v2_internal50_eval \
  --report-dir /tmp/v2_internal50_reports
```

Promotion and robustness gates:

```bash
python3 scripts/run_semantic_route_promotion_gate.py --help || true
python3 scripts/run_semantic_route_promotion_gate.py
python3 scripts/run_integrated_robustness_gate.py --help || true
python3 scripts/run_integrated_robustness_gate.py
python3 scripts/run_hidden_style_eval.py --help || true
python3 scripts/run_hidden_style_eval.py
```

Safety/leakage checks:

```bash
rg -n "gold_answer|organizer|oracle|expected_trace|query_id|example_id|hardcoded|unsupported_claims|LIVE_EMPTY|API_ERROR|local snapshot|current platform|live state" dashagent tests scripts . || true
python3 scripts/audit_hardcoded_runtime_and_score_paths.py
python3 scripts/audit_score_provenance.py
```

## Local Validation

| Check | Result |
|---|---:|
| `python3 -m pytest -q` | 888 passed, 1 skipped |
| `python3 scripts/check_submission_ready.py` | ok=True |
| Packaged default | SQL_FIRST_API_VERIFY |
| Query output count | 73 |
| Secret scan | ok=True |
| `git diff --check` | passed |

## Boundary Trace Checks

| Prompt | Route | SQL | API | Bypass | EvidenceBus | Post-Evidence Router | Expected? |
|---|---|---:|---:|---|---|---|---|
| What is a schema? | LLM_SAFE_DIRECT | 0 | 0 | true | false | false | yes |
| In the phrase 'list schemas', what does 'list' mean? | LLM_SAFE_DIRECT | 0 | 0 | true | false | false | yes |
| Explain what inactive journey means and show inactive journeys. | SQL_THEN_API | 1 | 1 | false | true | true | yes |
| What schemas do I have? | SQL_ONLY | 1 | 1 | false | true | true | yes |
| How many schema records are in the local snapshot? | SQL_ONLY | 1 | 0 | false | true | true | yes |
| When was the journey 'Birthday Message' published? | SQL_THEN_API | 1 | 1 | false | true | true | yes |

Boundary trace final answers:

- What is a schema?  
  `A schema is a blueprint for how data is structured: it defines fields, types, and constraints so systems can interpret records consistently.`

- In the phrase 'list schemas', what does 'list' mean?  
  `In that phrase, list means to return or enumerate matching items; this is a wording question, not a request to query schema records.`

- Explain what inactive journey means and show inactive journeys.  
  `An inactive journey is a journey that is not currently active or running. Journeys: Birthday Message (updated); Gold Tier Welcome Email (created). API unavailable/error; cannot verify live state. Live API verification was not executed because Adobe credentials are unavailable.`

- What schemas do I have?  
  `API unavailable/error; cannot verify live state.`

- How many schema records are in the local snapshot?  
  `There are 74 schema records in the local snapshot.`

- When was the journey 'Birthday Message' published?  
  `The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and live API verification was not executed because Adobe credentials are unavailable.`

## Organizer35 Strict Comparison

The Organizer35 strict run used the existing repo command with `--allow-live-diagnostic-without-success` because the live API guard reported `live_success_count=0`. The run is diagnostic-only and is not an official promotion score claim.

| Strategy | Final | Correctness | Answer | SQL | API | Tool Calls | Runtime | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6577 | 0.6850 | 0.3207 | 0.9333 | 0.9791 | 1.4571 | 0.6407 | 827.9714 |
| ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 | 0.6461 | 0.6749 | 0.3156 | 0.9333 | 0.9591 | 1.4000 | 0.4956 | 1154.9714 |

Live API guard caveat:

| Field | Value |
|---|---|
| diagnostic_only | true |
| live_success_count | 0 |
| override_used | true |
| official_score_claim | false |
| promotion_allowed | false |
| reason | explicit_user_diagnostic_run_without_live_success |

## Organizer35 Delta

| Metric | V2 - SQL_FIRST |
|---|---:|
| Final | -0.0116 |
| Correctness | -0.0101 |
| Answer | -0.0051 |
| SQL | 0.0000 |
| API | -0.0200 |
| Tool Calls | -0.0571 |
| Runtime | -0.1451 |
| Tokens | +327.0000 |

Interpretation: V2 is slightly more efficient on Organizer35 tool count and runtime, but it trails SQL_FIRST on final score, correctness, answer, and API score.

## Internal50 Focused Subset

| Strategy | Combined | Behavior | Answer Grounding | SQL Calls | API Calls | no_tool_fp | api_required_underuse | unsupported_claims | Runtime ms | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| packaged_baseline_real | 0.7168 | 0.8238 | 1.0000 | 40 | 33 | 0 | 0 | 0 | 36.7769 | 1019.34 |
| robust_generalized_harness_candidate_v2_real | 0.7784 | 0.8525 | 1.0000 | 38 | 26 | 0 | 0 | 0 | 188.7269 | 972.12 |

## Internal50 Delta

| Metric | Delta |
|---|---:|
| Overall / combined diagnostic | +0.0616 |
| Behavior | +0.0287 |
| Rows helped | 8 |
| Rows hurt | 0 |
| Rows neutral | 42 |
| SQL call delta | -2 |
| API call delta | -7 |
| Unsupported claim delta | 0 |
| Runtime delta ms | +151.9500 |
| Token delta | -47.2200 |

Internal50 gate result:

| Field | Value |
|---|---|
| passed | false |
| recommendation | latest_applied_real_trial_unavailable_keep_shadow |
| blockers | Semantic route decisions are integrated as shadow checkpoints only; staged evidence policy is shadow-only; post-SQL API policy records advice but does not alter actual API execution; no non-shadow promotion gate has approved packaged execution changes. |

## Tool-Call Efficiency Ablation

Organizer35:

- SQL_FIRST_API_VERIFY average tool calls: 1.4571
- V2 average tool calls: 1.4000
- Delta: -0.0571

Internal50:

- Baseline SQL/API calls: 40 SQL, 33 API
- V2 SQL/API calls: 38 SQL, 26 API
- Delta: -2 SQL, -7 API

Interpretation:

- V2 reduces tool calls on both Organizer35 and Internal50.
- V2 reduces SQL and API calls on Internal50.
- V2 does not introduce no-tool false positives or API_REQUIRED underuse on Internal50.
- V2 still has an Organizer35 API score regression of -0.0200, so the tool savings are not enough to justify promotion.
- Internal50 runtime is slower by about +151.95 ms despite fewer tool calls, likely due research-line routing/checkpoint overhead.

## Safety / Hallucination Ablation

| Safety check | Result |
|---|---|
| Internal50 no_tool_fp | 0 |
| Internal50 api_required_underuse | 0 |
| Internal50 unsupported_claims | 0 |
| Semantic gate: no_concrete_data_plain_llm_direct | true |
| Semantic gate: hidden_style_passes | true |
| Semantic gate: packaged_runtime_unchanged | true |
| Score provenance: runtime_gold_visible_count | 0 |
| Hardcode audit: unsafe_fake_score_count | 0 |
| Hardcode audit: unsafe_runtime_hardcode_count | 2 |

Hardcode audit details:

| Path | Line | Finding |
|---|---:|---|
| dashagent/concise_llm_answer_rewriter.py | 144 | Example string: `Inactive journeys: Birthday Message; Gold Tier Welcome Email.` |
| dashagent/executor.py | 1252 | Checkpoint technique text: `one-shot concise gold-style LLM rewrite` |

Interpretation:

- The current routing-boundary behavior did not introduce no-tool false positives, API_REQUIRED underuse, or unsupported claims in the focused Internal50 run.
- The broad safety search found many hits because it scanned tests, scripts, reports, and generated outputs. The structured audit is more actionable: zero fake-score hits, runtime_gold_visible_count=0, and two pre-existing concise-rewrite hardcode/string findings.
- The two hardcode audit findings are promotion blockers, but they are not specific to the routing-boundary bypass behavior.
- Full pytest passed, including existing verifier coverage for API_ERROR/LIVE_EMPTY semantics. The routing-boundary patch does not change API_ERROR or LIVE_EMPTY rendering logic.

## Promotion Gate

Semantic route promotion gate:

| Gate | Passed |
|---|---|
| broad_semantic_router_promotion_blocked | true |
| check_submission_ready_passes | true |
| conceptual_keyword_prompts_skip_tools_safely | true |
| endpoint_matrix_clean | true |
| final_submission_format_unchanged | true |
| generated_prompt_unsupported_claims_zero | true |
| hidden_style_passes | true |
| no_concrete_data_plain_llm_direct | true |
| no_increase_false_no_tool_risk | true |
| packaged_runtime_unchanged | true |
| public_dev_strict_no_regression | true |
| shadow_false_positive_reduction | true |
| tool_runtime_token_cost_improves_or_stable | true |

Promotion result:

| Field | Value |
|---|---|
| promotion_allowed | false |
| recommendation | keep_shadow_only |

Interpretation: the route gate says the research route should remain shadow-only.

## Integrated / Hidden Gates

Integrated robustness gate:

| Field | Value |
|---|---|
| recommendation | blocked_by_robustness_regression |
| promotion_allowed | false |
| strict_score_non_regression | failed |
| strict_score_non_regression observed | 0.6513 |
| hidden_style_passes | true |

Hidden-style eval:

| Metric | Value |
|---|---:|
| total_cases | 48 |
| passed_cases | 48 |
| failed_cases | 0 |
| family_stability_rate | 1.0 |
| schema_stability_rate | 1.0 |

## Ablation Summary Table

| Ablation / Check | Purpose | Command / Check | Result | Interpretation |
|---|---|---|---|---|
| Pure concept bypass | Verify high-confidence concept skips evidence | V2 trace: `What is a schema?` | SQL 0, API 0, bypass true, EvidenceBus false | Pass |
| Pure meta bypass | Verify language/meta prompt skips evidence | V2 trace: `In the phrase 'list schemas'...` | SQL 0, API 0, bypass true, EvidenceBus false | Pass |
| Mixed prompt evidence path | Ensure mixed concept+data does not bypass | V2 trace: inactive journey mixed prompt | SQL 1, API 1, EvidenceBus true | Pass |
| Ambiguous data-like evidence path | Ensure user-specific broad data prompt does not bypass | V2 trace: `What schemas do I have?` | SQL 1, API 1, EvidenceBus true | Pass |
| Local snapshot count | Ensure count prompt uses evidence | V2 trace: local schema count | SQL 1, API 0, EvidenceBus true | Pass |
| Concrete date/entity | Ensure date/entity prompt uses evidence | V2 trace: Birthday Message published | SQL 1, API 1, EvidenceBus true | Pass |
| Organizer35 SQL_FIRST vs V2 | Public strict comparison | `run_dev_eval.py --strict ...` | V2 final -0.0116 vs SQL_FIRST | Not promotable |
| Internal50 baseline vs V2 | Focused generalization subset | `run_dashagent_500_prompt_suite_eval.py ... --limit 50` | V2 combined +0.0616, helped/hurt/neutral 8/0/42 | Useful shadow improvement |
| Tool-call efficiency | Compare tool/API/SQL call costs | Organizer35 + Internal50 summaries | Organizer tool calls -0.0571; Internal SQL -2/API -7 | Better tool efficiency |
| Safety/no hallucination | Check no-tool FP, API underuse, unsupported claims | Internal50 + gates + audits | no_tool_fp 0, api_required_underuse 0, unsupported_claims 0 | Safe in focused runs |
| Promotion gate | Determine promotion readiness | `run_semantic_route_promotion_gate.py` | promotion_allowed false, keep_shadow_only | Do not promote |

## Final Recommendation

Safe to keep: yes.

Safe to commit: yes, as a research/shadow routing-boundary patch. It is locally tested, check_submission_ready passes, hidden-style passes, and the boundary trace checks match the intended behavior.

Safe to promote: no.

Reason: Organizer35 V2 still trails SQL_FIRST_API_VERIFY on final score (-0.0116), correctness (-0.0101), answer (-0.0051), and API score (-0.0200). The semantic promotion gate explicitly returns `promotion_allowed=false` with recommendation `keep_shadow_only`, and the integrated robustness gate returns `blocked_by_robustness_regression`.

Operational recommendation: keep SQL_FIRST_API_VERIFY as packaged default. Keep ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 explicit/shadow-only. Use V2 as a research line because it shows better Internal50 behavior and lower tool-call usage, but do not promote it until Organizer35 and robustness gates stop regressing.

## Remaining Risks

1. Organizer35 regression remains: V2 final score is 0.6461 vs SQL_FIRST 0.6577.
2. V2 API score is lower on Organizer35: 0.9591 vs SQL_FIRST 0.9791.
3. V2 answer score is slightly lower: 0.3156 vs 0.3207.
4. Internal50 runtime is higher by about +151.95 ms despite lower SQL/API calls.
5. Hardcode audit reports two existing promotion blockers in the concise rewrite path.
6. Organizer35 strict run used diagnostic override because live_success_count=0, so it is diagnostic-only and not an official live promotion score.
7. The routing boundary itself looks safe, but V2 as a whole still needs more work before promotion.

## Copy-Paste English Summary for Senior Student

I ran the V2 routing-boundary ablation suite. The boundary behavior is correct: pure high-confidence concept/meta prompts bypass SQL/API/EvidenceBus/post-evidence answer routing, while mixed, ambiguous data-like, count, status/date/entity, and user-specific prompts still use the evidence path. Local validation passes with 888 tests passed and 1 skipped, check_submission_ready passes, and hidden-style eval passes 48/48. Internal50 improves from 0.7168 to 0.7784 combined diagnostic score, helps 8 rows, hurts 0 rows, and reduces SQL/API calls by -2/-7 with no no-tool false positives, API_REQUIRED underuse, or unsupported claims. However, Organizer35 still regresses versus SQL_FIRST_API_VERIFY: final 0.6461 vs 0.6577, answer 0.3156 vs 0.3207, API 0.9591 vs 0.9791. The semantic promotion gate says promotion_allowed=false and recommendation=keep_shadow_only, and the integrated robustness gate is blocked by strict-score regression. Recommendation: safe to keep and commit as a research/shadow patch, but not safe to promote; SQL_FIRST_API_VERIFY should remain the packaged default.

## Copy-Paste Chinese Summary for Senior Student

我已经跑完 V2 routing-boundary 的消融和验证。这个边界本身是正确的：高置信度的纯概念/元语言问题会绕过 SQL、API、EvidenceBus 和 post-evidence answer router；混合问题、模糊但像数据的问题、count/status/date/entity/user-specific 这类问题仍然进入 evidence path。本地验证通过：pytest 是 888 passed、1 skipped，check_submission_ready 通过，hidden-style 是 48/48。Internal50 上 V2 从 0.7168 提升到 0.7784，8 条变好、0 条变差，并且 SQL/API 调用减少了 -2/-7，没有 no-tool false positive、API_REQUIRED underuse 或 unsupported claims。但是 Organizer35 上 V2 仍然低于 SQL_FIRST_API_VERIFY：final 0.6461 vs 0.6577，answer 0.3156 vs 0.3207，API 0.9591 vs 0.9791。promotion gate 明确给出 promotion_allowed=false、recommendation=keep_shadow_only，integrated robustness gate 也因为 strict score regression 被阻断。结论：这个 patch 可以保留、可以提交，作为 research/shadow 线是安全的；但现在不能 promote，packaged default 仍然应该保持 SQL_FIRST_API_VERIFY。
