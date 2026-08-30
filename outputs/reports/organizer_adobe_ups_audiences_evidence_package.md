# Organizer Adobe UPS Audiences Evidence Package

Fully redacted evidence package for the organizer-provided UPS audiences smoke test.

## A. Test Identity

- test_name: `organizer_adobe_ups_audiences_smoke`
- endpoint_purpose: `UPS audiences read-only validation`
- data_endpoint_method: `GET`
- data_endpoint_path: `/data/core/ups/audiences`
- data_endpoint_params: `{'limit': 5}`
- data_endpoint_mutating: `False`
- direct_path_tested: `True`
- repo_client_path_tested: `True`
- generated_at: `2026-05-24T18:01:26.954372+00:00`

## B. Credential Loading Status

- env_file_loaded: `True`
- auth_mode: `client_credentials`
- client_id_source: `alias`
- client_secret_source: `alias`
- org_id_source: `alias`
- sandbox_source: `alias`
- base_url_source: `primary`
- scopes_source: `default`
- same_resolved_config_used_for_direct_and_repo_paths: `True`

## C. Token Acquisition Evidence

- token_request_attempted: `True`
- token_request_method: `POST`
- token_request_url_host: `ims-na1.adobelogin.com`
- grant_type: `client_credentials`
- token_status_code: `200`
- token_json_parse_ok: `True`
- access_token_field_present: `True`
- token_acquisition_ok: `True`
- expires_in_present: `True`
- token_error_category: `None`

## D. Direct Organizer-Style Requests Path

- request_attempted: `True`
- method: `GET`
- base_url_host: `platform.adobe.io`
- path: `/data/core/ups/audiences`
- params: `{'limit': 5}`
- header_names_sent: `['Authorization', 'Content-Type', 'x-api-key', 'x-gw-ims-org-id', 'x-sandbox-name']`
- header_values_redacted: `True`
- status_code: `500`
- json_parse_ok: `True`
- outcome: `external_api_unavailable`
- response_content_type: `None`
- safe_response_error_fields: `{'error_code': '500', 'error_message': "com.fasterxml.jackson.core.JsonParseException: Unexpected character ('<' (code 60)): expected a valid value (JSON String, Number, Array, Object or token 'null', 'true' or 'false') at [Source: REDACTED (`StreamReadFeature.INCLUDE_SOURCE_IN_L", 'title': 'Internal Server Error', 'status': '500'}`
- adobe_diagnostic_ids: `{}`
- redacted_response_excerpt: `{"code": "500", "detail": "com.fasterxml.jackson.core.JsonParseException: Unexpected character ('<' (code 60)): expected a valid value (JSON String, Number, Array, Object or token 'null', 'true' or 'false')\n at [Source: REDACTED (`StreamReadFeature.INCLUDE_SOURCE_IN_LOCATION` disabled); line: 1, column: 1]", "status": 500, "title": "Internal Server Error"}`

## E. Repo AdobeAPIClient Path

- request_attempted: `True`
- method: `GET`
- base_url_host: `platform.adobe.io`
- path: `/data/core/ups/audiences`
- params: `{'limit': 5}`
- header_names_sent: `['Authorization', 'Content-Type', 'x-api-key', 'x-gw-ims-org-id', 'x-sandbox-name']`
- header_values_redacted: `True`
- status_code: `500`
- json_parse_ok: `True`
- outcome: `external_api_unavailable`
- response_content_type: `None`
- safe_response_error_fields: `{'error_code': '500', 'error_message': "com.fasterxml.jackson.core.JsonParseException: Unexpected character ('<' (code 60)): expected a valid value (JSON String, Number, Array, Object or token 'null', 'true' or 'false') at [Source: REDACTED (`StreamReadFeature.INCLUDE_SOURCE_IN_L", 'title': 'Internal Server Error', 'status': '500'}`
- adobe_diagnostic_ids: `{}`
- redacted_response_excerpt: `{"code": "500", "detail": "com.fasterxml.jackson.core.JsonParseException: Unexpected character ('<' (code 60)): expected a valid value (JSON String, Number, Array, Object or token 'null', 'true' or 'false')\n at [Source: REDACTED (`StreamReadFeature.INCLUDE_SOURCE_IN_LOCATION` disabled); line: 1, column: 1]", "status": 500, "title": "Internal Server Error"}`

## F. Equivalence Verification

- same_method: `True`
- same_path: `True`
- same_params: `True`
- same_required_header_names: `True`
- same_credential_sources: `True`
- same_status_code: `True`
- same_outcome: `True`
- same_safe_error_shape: `True`
- comparison_result: `both_same_failure`

## G. Evidence-Based Conclusion

- conclusion: `both_paths_failed_equivalently_no_repo_specific_mismatch_shown`

Both the organizer-style direct request and the repo AdobeAPIClient request failed with the same HTTP status/outcome. This does not show a repo-specific header/client mismatch. Root cause may still be Adobe endpoint availability, sandbox, organization context, or product-profile permission.
