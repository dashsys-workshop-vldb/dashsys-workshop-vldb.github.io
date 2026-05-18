# Correctness + Efficiency Scorecard

- Organizer weights known: `False`
- Official overall score claim: `False`
- Baseline strategy: `SQL_FIRST_API_VERIFY`
- Baseline correctness score: `0.6805`
- Baseline strict final score: `0.6553`

## Formulas

- tool_call_efficiency = baseline_tool_calls / max(variant_tool_calls, 1)
- token_efficiency = baseline_tokens / max(variant_tokens, 1)
- runtime_efficiency = baseline_runtime / max(variant_runtime, 0.001)
- turns_efficiency = baseline_turns / max(variant_turns, 1), or neutral 1.0 when turns are unavailable
- each efficiency ratio is capped to [0.0, 1.25]
- efficiency_score_equal_weight = average(turns_efficiency, tool_call_efficiency, token_efficiency, runtime_efficiency)
- correctness_dominant = 0.80 * correctness_score + 0.20 * efficiency_score_equal_weight
- balanced = 0.60 * correctness_score + 0.40 * efficiency_score_equal_weight
- efficiency_sensitive = 0.50 * correctness_score + 0.50 * efficiency_score_equal_weight

## Variant Sensitivity

| Variant | Correctness delta | Efficiency | Pareto dominates baseline | Promotion candidate status |
| --- | ---: | ---: | --- | --- |
| `compact_tool_schema` | 0.0 | 1.0415 | True | `efficiency_candidate_needs_strict_validation` |
| `allowed_tools_by_prompt_type` | 0.0 | 1.125 | True | `efficiency_candidate_needs_strict_validation` |
| `tool_choice_policy` | 0.0 | 1.125 | True | `efficiency_candidate_needs_strict_validation` |
| `disable_parallel_tool_calls` | 0.0 | 1.0 | False | `keep_shadow_only` |
| `compact_tool_result_evidence_summary` | 0.0 | 1.0486 | True | `efficiency_candidate_needs_strict_validation` |
| `rewrite_gate_strict` | 0.0 | 1.0 | False | `keep_shadow_only` |
| `no_rewrite_when_backend_complete` | 0.0 | 1.0126 | True | `efficiency_candidate_needs_strict_validation` |
| `combined_safe_tool_policy` | 0.0 | 1.167 | True | `efficiency_candidate_needs_strict_validation` |
| `sql_required_value_answer_slots` | 0.0 | 0.9993 | False | `reject` |
| `zero_row_local_evidence_clarity` | -0.0054 | 1.0005 | False | `reject` |
| `dry_run_caveat_after_sql_answer` | -0.015 | 1.0028 | False | `reject` |
| `answer_intent_count_list_status_guard` | -0.0129 | 1.0015 | False | `reject` |
| `combined_minimal` | -0.0163 | 1.0028 | False | `reject` |

## Decision

- Decision: `speed_only_patch_needs_validation`
- Best candidate: `compact_tool_schema`

Composite scenarios are sensitivity analysis only; no official ranking improvement is claimed.
