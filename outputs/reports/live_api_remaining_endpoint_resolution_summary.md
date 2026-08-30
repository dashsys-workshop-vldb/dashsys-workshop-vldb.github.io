# Live API Remaining Endpoint Resolution Summary

- Runtime-relevant endpoint path failures remain: `False`
- Unexplained runtime-selectable endpoint path issue count: `0`
- Denominator changed: `False`

## Before Totals

- total_safe_get_endpoints_attempted: `15`
- live_success_count: `8`
- live_empty_count: `4`
- auth_error_count: `0`
- sandbox_scope_issue_count: `0`
- endpoint_path_issue_count: `3`
- external_api_unavailable_count: `0`
- malformed_response_count: `0`
- api_error_count: `0`
- usable_live_payload_endpoint_count: `8`

## After Totals

- total_safe_get_endpoints_attempted: `15`
- live_success_count: `10`
- live_empty_count: `5`
- auth_error_count: `0`
- sandbox_scope_issue_count: `0`
- endpoint_path_issue_count: `0`
- external_api_unavailable_count: `0`
- malformed_response_count: `0`
- api_error_count: `0`
- usable_live_payload_endpoint_count: `10`

## Resolutions

- `audit_events_short`: `safely_aliased_to_proven_canonical_endpoint`; `404` / `endpoint_path_issue` -> `200` / `live_empty`
- `unified_tags`: `fixed_with_proven_live_request_shape`; `404` / `endpoint_path_issue` -> `200` / `live_success`
- `unified_tag_categories`: `fixed_with_proven_live_request_shape`; `404` / `endpoint_path_issue` -> `200` / `live_success`

## Guarded E2E

- answer_used_api_state_count: `3`
- answer_used_usable_api_evidence_count: `9`
- api_failure_count: `0`
- api_state_forwarded_count: `12`
- live_api_calls_attempted: `12`
- live_empty_count: `3`
- live_success_count: `9`
- parser_evidencebus_failure_count: `0`
- parser_success_count: `12`
- trial_query_count: `12`
- unresolved_path_failure_count: `0`
- unsupported_api_claim_count: `0`
- usable_live_api_evidence_count: `9`
