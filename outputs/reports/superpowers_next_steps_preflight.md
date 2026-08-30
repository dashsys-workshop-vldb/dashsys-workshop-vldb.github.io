# Superpowers Next Steps Preflight

Disciplined preflight before manual local diagnostic review. This report does not change runtime behavior.

- Status: `complete`
- Blocker: `False`
- Packaged strategy: `SQL_FIRST_API_VERIFY`
- Strict score: `0.6553`
- Hidden-style: `{'label': '48/48', 'passed': 48, 'total': 48}`
- Final submission ready: `True`
- Live success count: `0`
- Local diagnostic: `250` pass / `0` fail
- Runtime changes allowed now: `False`

## Protected Artifacts

- `outputs/final_submission/**`
- `outputs/eval_results_strict.json`
- `outputs/hidden_style_eval.*`
- `outputs/final_submission_manifest.json`
- `final_submission_manifest.json`
- `dashagent/endpoint_catalog.py`
- `dashagent/config.py`
- `scripts/package_query_outputs.py`
- `scripts/run_dev_eval.py`

## Candidate Categories To Inspect

- zero_row_sql / dataflow_run
- missing_count_or_name_advisory / segment_audience
- answer_intent_mismatch / segment_audience
- domain_mismatch / dataflow_run
- route_mismatch / destination_flow

## No-Change Safety Rule

Do not modify packaged defaults, endpoint catalog paths, validators, strict/hidden artifacts, or final submission unless the gated fix decision explicitly allows it.
