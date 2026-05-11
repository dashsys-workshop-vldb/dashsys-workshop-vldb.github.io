# Live Adobe API Readiness Audit

Infrastructure validation only; this report is not official strict-score evidence.

- Overall status: `warning`
- Critical failures: `0`
- Warnings: `1`
- Official score claim: `False`
- Packaged runtime affected: `False`
- Manual token refresh required: `True`

## Credential Presence

- `access_token_env`: `{'present': False, 'env_name': None}`
- `api_key_env`: `{'present': False, 'env_name': None}`
- `client_id_env`: `{'present': False, 'env_name': None}`
- `client_credential_env`: `{'present': False, 'env_name': None}`
- `org_id_env`: `{'present': False, 'env_name': None}`
- `sandbox_name_env`: `{'present': False, 'env_name': None}`
- `base_url_env`: `{'present': False, 'env_name': None}`
- `masked_org_id`: `None`
- `masked_sandbox_name`: `None`

## Audit Items

- `pass` `credential_env_aliases`: Credential loading supports ADOBE_* aliases plus existing legacy names.
  Evidence: `dashagent/api_client.py`
  Explanation: AdobeCredentials.from_env reads ADOBE_ACCESS_TOKEN/ACCESS_TOKEN, ADOBE_API_KEY/CLIENT_ID, ADOBE_ORG_ID/IMS_ORG, ADOBE_SANDBOX_NAME/SANDBOX, ADOBE_BASE_URL, and ADOBE_CLIENT_ID/SECRET.
- `pass` `required_headers`: call_api can attach Authorization, x-api-key, x-gw-ims-org-id, x-sandbox-name, and Content-Type.
  Evidence: `dashagent/api_client.py`
  Explanation: Header keys available: ['Authorization', 'Content-Type', 'x-api-key', 'x-gw-ims-org-id', 'x-sandbox-name']; values are redacted or masked in reports.
- `warning` `manual_token_refresh`: Refreshed access tokens can be supplied through env; automated refresh is optional.
  Evidence: `dashagent/api_client.py`
  Explanation: Manual token refresh is required when no access token is present. Client-credentials token generation remains available through ADOBE_CLIENT_ID/SECRET or CLIENT_ID/SECRET.
- `pass` `endpoint_catalog_coverage`: Endpoint catalog documents method, path, params, family, and path-param discovery needs.
  Evidence: `dashagent/endpoint_catalog.py`
  Explanation: 21 catalog endpoints are available; GET endpoints with unresolved path params are marked discovery-required.
- `pass` `call_api_interface`: call_api(method, url, params, headers) exists and is the Adobe REST execution path.
  Evidence: `dashagent/api_client.py`
  Explanation: AdobeAPIClient.call_api exposes method/url/params/headers and preserves dry-run/live result labels.
- `pass` `api_validator_path`: API calls go through endpoint catalog validation before execution.
  Evidence: `dashagent/validators.py`
  Explanation: APIValidator validates catalog-approved paths and blocks unresolved placeholders.
- `pass` `live_dry_run_separation`: Credentials present allow live mode; missing credentials use honest dry-run fallback.
  Evidence: `dashagent/api_client.py`
  Explanation: Current credentials present: False; missing-credential client dry_run=True; fake-token client dry_run=False.
- `pass` `response_parser_readiness`: API response parser distinguishes live empty results, dry-run unavailability, and live errors.
  Evidence: `dashagent/api_response_parser.py`
  Explanation: Structured parser extracts ids, names, statuses, counts, timestamps, pagination, errors, and redacted previews.
- `pass` `evidencebus_api_flow`: Real API evidence can flow through EvidenceBus, answer slots, answer synthesis, and trajectory logging.
  Evidence: `dashagent/evidence_bus.py; dashagent/answer_slots.py; dashagent/trajectory.py`
  Explanation: EvidenceBus and answer slots consume normalize_api_evidence, which now understands parsed_evidence from the live API parser.
- `pass` `error_handling`: Live API error states are represented without confusing them with dry-run fallback.
  Evidence: `dashagent/api_client.py; dashagent/api_response_parser.py`
  Explanation: HTTP non-OK responses set dry_run=false and parsed_evidence.evidence_state=api_error; exceptions also produce api_error.
- `pass` `credential_secret_safety`: Tokens, API keys, client secrets, org IDs, sandbox names, and Authorization headers are not exposed in reports/trajectories.
  Evidence: `dashagent/trajectory.py`
  Explanation: Access tokens, API keys, and secrets are fully redacted; org ID and sandbox name are masked by default.
- `pass` `diagnostic_output_isolation`: Live smoke/trial outputs must not overwrite strict eval, eval directories, final_submission, or final_submission_manifest.
  Evidence: `scripts/run_live_api_readiness_smoke.py; scripts/run_live_api_evidence_pipeline_trial.py`
  Explanation: Readiness scripts write reports and isolated trial artifacts only.

## Endpoint Smoke Eligibility

- `journey_list` GET `/ajo/journey` smoke_eligible=True discovery_required=False
- `ups_audiences` GET `/data/core/ups/audiences` smoke_eligible=True discovery_required=False
- `segment_definitions` GET `/data/core/ups/segment/definitions` smoke_eligible=True discovery_required=False
- `flowservice_flows` GET `/data/foundation/flowservice/flows` smoke_eligible=True discovery_required=False
- `flowservice_runs` GET `/data/foundation/flowservice/runs` smoke_eligible=True discovery_required=False
- `catalog_datasets` GET `/data/foundation/catalog/dataSets` smoke_eligible=True discovery_required=False
- `schema_registry_schema` GET `/data/foundation/schemaregistry/tenant/schemas/{schema_id}` smoke_eligible=False discovery_required=True
- `schema_registry_schemas` GET `/data/foundation/schemaregistry/tenant/schemas` smoke_eligible=True discovery_required=False
- `schemas_short` GET `/schemas` smoke_eligible=True discovery_required=False
- `audit_events` GET `/data/foundation/audit/events` smoke_eligible=True discovery_required=False
- `audit_events_short` GET `/audit/events` smoke_eligible=True discovery_required=False
- `unified_tags` GET `/unifiedtags/tags` smoke_eligible=True discovery_required=False
- `unified_tag_categories` GET `/unifiedtags/tagCategory` smoke_eligible=True discovery_required=False
- `unified_tag_detail` GET `/unifiedtags/tags/{tag_id}` smoke_eligible=False discovery_required=True
- `merge_policies` GET `/data/core/ups/config/mergePolicies` smoke_eligible=True discovery_required=False
- `segment_jobs` GET `/data/core/ups/segment/jobs` smoke_eligible=True discovery_required=False
- `catalog_batches` GET `/data/foundation/catalog/batches` smoke_eligible=True discovery_required=False
- `catalog_batch_detail` GET `/data/foundation/catalog/batches/{batch_id}` smoke_eligible=False discovery_required=True
- `export_batch_files` GET `/data/foundation/export/batches/{batch_id}/files` smoke_eligible=False discovery_required=True
- `export_batch_failed` GET `/data/foundation/export/batches/{batch_id}/failed` smoke_eligible=False discovery_required=True
- `observability_metrics` POST `/data/infrastructure/observability/insights/metrics` smoke_eligible=False discovery_required=False
