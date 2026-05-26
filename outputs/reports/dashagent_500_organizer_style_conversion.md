# DashAgent 500 Organizer-Style Conversion

- Converted examples: `500`
- Output dataset: `/Users/tanqinyang/Desktop/dashsys-workshop-vldb/data/benchmarks/dashagent_500_organizer_style.json`
- Manifest: `/Users/tanqinyang/Desktop/dashsys-workshop-vldb/data/benchmarks/dashagent_500_organizer_style_manifest.json`
- Organizer-equivalent: `False`
- Endpoint mapping failures: `0`
- Runtime category/tags exposed: `False`
- Gold hidden from runtime: `True`

## Category Distribution

- `ambiguous_low_confidence`: 40
- `api_only_live_platform`: 90
- `conceptual_no_tool`: 60
- `hard_stress`: 60
- `mixed_conceptual_data`: 40
- `sql_only_local_snapshot`: 120
- `sql_then_api_verification`: 90

## Evidence Need Distribution

- `api`: 112
- `mixed`: 53
- `none`: 70
- `sql`: 162
- `sql_then_api`: 103

## Sidecar / Lost Strict Fields

- `acceptable_answer_variants_sidecar_only`: 500
- `expected_observable_trace_sidecar_only`: 500
- `expected_tool_calls_sidecar_only`: 500
- `forbidden_claims_sidecar_only`: 500
- `grading_rubric_sidecar_only`: 500
- `required_facts_sidecar_only`: 500

## Notes

- Converted rows expose only id/query to the agent runtime through EvalHarness.
- Gold SQL/API/answer fields are used only by the strict evaluator after execution.
- Expected observable traces and detailed rubric fields are retained in the original benchmark gold, not embedded as runtime inputs.
