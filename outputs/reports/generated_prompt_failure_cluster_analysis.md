# Generated Prompt Failure Cluster Analysis

Generated prompts remain diagnostic-only. This report clusters failure signatures to decide which isolated trials are worth running.

- Total rows: `250`
- Cluster counts: `{'answer_shape_weak': 88, 'route_mismatch': 86, 'api_endpoint_selection_gap': 57, 'no_clear_failure': 17, 'no_template_fallback_weak': 2}`

## route_mismatch

- Count: `86`
- Root cause: Generated diagnostic labels often disagree with deterministic route decisions; some are likely label noise and require manual review before router edits.
- Safest fix type: `manual label-noise review before conservative synonym/calibration rule`
- Generalization risk: `medium`

## answer_shape_weak

- Count: `88`
- Root cause: Evidence is available and unsupported claims are zero, but deterministic answer wording does not always expose the count/list/status/date shape expected by the prompt.
- Safest fix type: `targeted deterministic answer template trial`
- Generalization risk: `low`

## api_endpoint_selection_gap

- Count: `57`
- Root cause: The runtime sometimes calls a less useful API family or carries unresolved/low-yield optional API calls when SQL evidence already answers the question.
- Safest fix type: `endpoint-family ranking and optional API suppression trial`
- Generalization risk: `medium`

## no_template_fallback_weak

- Count: `2`
- Root cause: Template misses rely on heuristic fallback that can validate and execute but may select weak filters or produce zero-row evidence.
- Safest fix type: `schema-aware SQL gating diagnostic only`
- Generalization risk: `medium`

## no_clear_failure

- Count: `17`
- Root cause: No high-risk failure signature is present in available diagnostic fields.
- Safest fix type: `no_code_change`
- Generalization risk: `low`
