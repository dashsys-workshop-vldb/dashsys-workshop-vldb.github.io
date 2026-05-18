# SDK Tool Calling Optimization Trials

- Diagnostic only: `True`
- Baseline strict score: `0.6553`
- Writes official eval artifacts: `False`
- Writes final submission: `False`

| Variant | Strict delta | Token delta | Tool delta | Runtime delta | Recommendation |
| --- | ---: | ---: | ---: | ---: | --- |
| `compact_tool_schema` | 0.0 | -60 | 0 | -0.001 | `speed_safe_candidate_shadow_only` |
| `allowed_tools_by_prompt_type` | 0.0 | 0 | -4 | -0.04 | `speed_safe_candidate_shadow_only` |
| `tool_choice_policy` | 0.0 | 0 | -2 | -0.02 | `speed_safe_candidate_shadow_only` |
| `disable_parallel_tool_calls` | 0.0 | 0 | 0 | 0.0 | `keep_shadow_only` |
| `compact_tool_result_evidence_summary` | 0.0 | -80 | 0 | -0.001 | `speed_safe_candidate_shadow_only` |
| `rewrite_gate_strict` | 0.0 | 0 | 0 | 0.0 | `keep_shadow_only` |
| `no_rewrite_when_backend_complete` | 0.0 | -40 | 0 | 0.0 | `speed_safe_candidate_shadow_only` |
| `combined_safe_tool_policy` | 0.0 | -150 | -3 | -0.03 | `speed_safe_candidate_shadow_only` |
