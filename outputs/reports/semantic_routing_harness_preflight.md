# Semantic Routing Harness Preflight

Classification: `diagnostic_only`.

This snapshot was recorded before adding the shadow-only semantic routing harness. The packaged strategy remains `SQL_FIRST_API_VERIFY`, and no runtime routing behavior or final-submission format was changed in this phase.

## Current Baseline

- Git status before pass: clean.
- Packaged strategy: `SQL_FIRST_API_VERIFY`.
- Strict score source: `outputs/eval_results_strict.json`.
- `SQL_FIRST_API_VERIFY` strict score: `0.652`.
- SQL/API/answer: `0.9333` / `0.9791` / `0.3207`.
- Hidden-style source: `outputs/hidden_style_eval.json`.
- Hidden-style: `48/48`.
- Fresh `check_submission_ready`: `ok=true`, default strategy confirmed.

## Endpoint And Generated Diagnostics

- Endpoint matrix source: `outputs/reports/live_api_safe_get_endpoint_matrix.json`.
- Safe GET endpoints attempted: `15`.
- Live success / live empty / API error: `10` / `5` / `0`.
- Generated diagnostic source: `outputs/reports/weak_model_generated_prompt_diagnostic.json`.
- Generated subset runtime pass rate: `1.0`.
- Generated subset unsupported claims: `0`.
- Generated subset SQL/API validation pass rate: `1.0` / `1.0`.

## Current Routing Behavior

The first routing layer is `dashagent.prompt_router.route_prompt`, and `dashagent.simple_prompt_gate.decide_simple_prompt` wraps it for simple no-tool handling. The existing SDK semantic routing helper is `dashagent.semantic_routing_helper`; it is default-off and shadow-only when enabled.

Observed keyword false-positive risk:

| Prompt | Current route | Simple gate |
|---|---:|---:|
| `What is a schema?` | `LOCAL_DB_ONLY` | `USE_DATA_PIPELINE` |
| `List schemas` | `LOCAL_DB_ONLY` | `USE_DATA_PIPELINE` |
| `Explain merge policy` | `API_ONLY` | `USE_DATA_PIPELINE` |
| `Describe Adobe tags` | `API_ONLY` | `USE_DATA_PIPELINE` |
| `Explain merge policy and list current merge policies` | `API_ONLY` | `USE_DATA_PIPELINE` |

## Shadow Flags Before Pass

The new semantic routing harness flags did not exist before this pass:

- `ENABLE_OBJECTIVE_PROMPT_FEATURES`
- `ENABLE_SEMANTIC_INTENT_CLASSIFIER`
- `ENABLE_SEMANTIC_ROUTE_DECISION_LADDER`
- `SEMANTIC_ROUTE_SHADOW_ONLY`
- `SEMANTIC_ROUTE_TIER2_DIAGNOSTIC`

Decision: proceed with a shadow-only semantic routing harness. Promotion is not allowed by this preflight.
