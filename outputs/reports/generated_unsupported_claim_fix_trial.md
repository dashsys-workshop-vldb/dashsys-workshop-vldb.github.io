# Generated Unsupported Claim Fix Trial

This is an isolated diagnostic trial. It does not change runtime behavior or claim promotion.

- Baseline unsupported claims: `0`
- Current strict score: `0.6567`
- Recommendation: `candidate_requires_full_gate_validation`
- Reason: Low-risk candidate exists but this script does not promote runtime behavior.

## Variants

### answer_guard_only

- Projected unsupported claims after: `14`
- Rows helped: `1`
- Risk: `low`
- Recommendation: `candidate_for_runtime_validation`

### api_state_payload_separation

- Projected unsupported claims after: `15`
- Rows helped: `0`
- Risk: `low`
- Recommendation: `do_not_promote`

### evidence_linking_fix

- Projected unsupported claims after: `15`
- Rows helped: `0`
- Risk: `medium`
- Recommendation: `do_not_promote`

### parser_field_fix

- Projected unsupported claims after: `15`
- Rows helped: `0`
- Risk: `medium`
- Recommendation: `do_not_promote`

### verifier_false_positive_fix

- Projected unsupported claims after: `1`
- Rows helped: `14`
- Risk: `low`
- Recommendation: `candidate_for_runtime_validation`

### combined_safe_unsupported_claim_fix

- Projected unsupported claims after: `0`
- Rows helped: `15`
- Risk: `low`
- Recommendation: `candidate_for_runtime_validation`
