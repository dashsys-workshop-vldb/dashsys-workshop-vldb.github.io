# Full Generated Prompt Suite Diagnostic

Generated prompts are diagnostic coverage only; this report is not official strict-score evidence.

- Total prompts: `250`
- Executed prompts: `250`
- Runtime pass count: `250`
- Runtime fail count: `0`
- Validation fail count: `0`
- Live API calls: `212`
- Live success count: `65`
- Live empty count: `8`
- Dry-run count: `0`
- Template hit rate: `0.32`
- Template miss rate: `0.68`
- Unsupported claim count: `15`
- Official strict score computed: `False`

## Route Distribution

- `API_ONLY`: `98`
- `SQL_AND_API_COMPARE`: `1`
- `SQL_ONLY`: `109`
- `SQL_THEN_API`: `42`

## Top Failure Categories

- `answer_shape_weak`: `88`
- `api_endpoint_selection_gap`: `57`
- `no_clear_failure`: `17`
- `no_template_fallback_weak`: `2`
- `route_mismatch`: `86`

## Coverage Notes

- Generated diagnostics do not enter final submission and do not affect packaged runtime.
