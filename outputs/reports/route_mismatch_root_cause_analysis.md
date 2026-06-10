# Route Mismatch Root-Cause Analysis

Generated route labels are diagnostic-only. This report separates likely label noise from conservative deterministic candidates.

- Mismatch count: `86`
- Likely causes: `{'ambiguous_domain_terms': 44, 'api_need_decision_gap': 33, 'no_template_fallback_route_gap': 4, 'generated_label_noise': 3, 'unnecessary_api_call_noise': 2}`

## Candidate Fix Trials

- `conservative_synonym_expansion`: affected rows `44`, recommendation `trial_only`
- `confidence_margin_gate`: affected rows `4`, recommendation `trial_only`
- `api_need_recalibration`: affected rows `33`, recommendation `trial_only`
- `endpoint_family_priority_fix`: affected rows `77`, recommendation `trial_only`
