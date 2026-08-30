# Organizer Adobe Request Template Diff

Generated at: `2026-05-24T17:58:26.319029+00:00`

This report compares only safe request structure and same/different booleans. Credential values, organization values, sandbox values, access tokens, and header values are intentionally omitted.

## Latest Local Result

- token_status_code: `200`
- token_acquisition_ok: `True`
- direct_status_code: `500`
- direct_outcome: `external_api_unavailable`
- repo_status_code: `500`
- repo_outcome: `external_api_unavailable`
- comparison_result: `both_same_failure`

## Mismatch Fields

- `previous_vs_latest.token_request_content_type`
- `latest_vs_repo.token_request_content_type`
- `latest_vs_repo.scopes`
- `resolved_config.direct_scopes_same_as_repo_scopes`

## Decision

- likely_root_cause: `latest_template_local_failure_not_repo_specific`
- code_change_required: `False`
- env_local_manual_update_required: `True`
- exact_next_action: Align local Adobe env aliases and primary variables with the organizer template values without changing source code.
