# SDK Tool-Call Optimization Variants

All variants are isolated and trial-only; no packaged runtime behavior changes are made by this audit.

| Variant | Expected impact | Risk | Affected signals | Promotion status |
| --- | --- | --- | ---: | --- |
| `compact_tool_schema` | token input reduction | `low` | 0 | `trial_only` |
| `allowed_tools_by_prompt_type` | tool-call reduction | `medium` | 4 | `trial_only` |
| `tool_choice_policy` | tool-call stability | `medium` | 2 | `trial_only` |
| `disable_parallel_tool_calls` | stability | `low` | 1 | `trial_only` |
| `compact_tool_result_evidence_summary` | token output reduction | `low` | 1 | `trial_only` |
| `rewrite_gate_strict` | unsupported claim reduction | `medium` | 0 | `trial_only` |
| `no_rewrite_when_backend_complete` | runtime/token reduction | `low` | 2 | `trial_only` |
| `combined_safe_tool_policy` | combined token/tool reduction | `medium` | 3 | `trial_only` |
