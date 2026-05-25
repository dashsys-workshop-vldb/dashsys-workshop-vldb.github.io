# Organizer Adobe UPS Audiences Smoke

Safe diagnostic implementation of the organizer token plus `/data/core/ups/audiences` smoke snippet.

- Auth mode: `client_credentials`
- Token status code: `200`
- Token acquisition ok: `True`
- Audiences status code: `500`
- Audiences outcome: `external_api_unavailable`
- Credential valid for token: `True`
- UPS audiences access valid: `False`
- Likely issue: `adobe_service_issue`
- Comparison conclusion: `both_same_failure`
- Next action: Rerun later or ask organizer whether Adobe service availability/rate limits are active.

## Environment Presence

- `client_id`: `present`
- `client_secret`: `present`
- `ims_org`: `present`
- `sandbox`: `present`
- `base_url`: `present`
- `token_url`: `present`
- `scopes`: `present`

## Side-by-Side Result

- Direct requests: token `True`, status `500`, outcome `external_api_unavailable`
- Repo client: token `True`, status `500`, outcome `external_api_unavailable`

Response excerpts are redacted and truncated. Raw credentials, tokens, header values, org values, and sandbox values are intentionally omitted.
