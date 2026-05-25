# Organizer Latest Working Template Smoke

Generated at: `2026-05-24T20:11:58.549882+00:00`

This is the isolated PATH B exact reproduction report. It reads `.env.organizer_latest.local` directly and does not fall back to old `.env.local` values or repo defaults for request-context fields.

- exact_reproduction_status: `exact`
- latest_env_file_loaded: `True`
- token_status_code: `200`
- token_acquisition_ok: `True`
- PATH B status/outcome: `200` / `live_success`
- PATH B live_success: `True`

## Fallback Flags

- old_env_fallback_used_for_ims_org: `False`
- old_env_fallback_used_for_sandbox: `False`
- old_env_fallback_used_for_scopes: `False`
- old_env_fallback_used_for_base_url: `False`
- old_env_fallback_used_for_token_url: `False`
- repo_default_fallback_used: `False`

## Safe Boolean Comparison

- org_same_old_vs_latest: `True`
- sandbox_same_old_vs_latest: `False`
- scopes_same_old_vs_latest: `True`
- token_content_type_same_old_vs_latest: `False`
- latest_matches_repo_client_org: `True`
- latest_matches_repo_client_sandbox: `False`
- latest_matches_repo_client_scopes: `False`

## PATH Results

### PATH_A_old_local_configuration

- attempted: `True`
- method: `GET`
- path: `/data/core/ups/audiences`
- params: `{'limit': 5}`
- status_code: `500`
- outcome: `external_api_unavailable`

### PATH_B_organizer_latest_exact_direct

- attempted: `True`
- method: `GET`
- path: `/data/core/ups/audiences`
- params: `{'limit': 5}`
- status_code: `200`
- outcome: `live_success`
- live_success: `True`
- redacted_response_excerpt: `{"_links": {"next": {"href": "@/audiences?start=1&limit=5&totalCount=82"}}, "_page": {"limit": 5, "next": "1", "pageOffset": "0", "pageSize": 5, "start": "0", "totalCount": 82, "totalPages": 17}, "children": [{"_etag": "39781b5e-ee1a-4c0c-a4f6-64a17bf2677b", "ansibleUiEnabled": false, "audienceId": "706ddcd9-12e2-4036-861b-6d58bebc4fa2", "createEpoch": 1776395696, "createdBy": "2E57262769D5626E0A495FBD@8ac11fe266602de4495fc7.e", "creationTime": 1776395696590, "dataGovernancePolicy": {"excludeOptOut": true}, "dataRefPaths": {"_xdm.context.profile": ["_adobepeakprogram.retailStorePropensities.propensityForLoyaltyProgram"]}, "definedOn": [{"$ref": "https://ns.adobe.com/xdm/context/profile__union", "meta:containerId": "a30a9c4e-327a-4d60-8a9c-4e327a6d60dd", "meta:resourceType": "unions"}], "dependencies": [], "dependents": [], "description": "Top-tier propensity for loyalty program enrollment above 0.8. Tests propensityForLoyaltyProgram at a higher threshold.", "evaluationInfo": {"batch": `

### PATH_C_repo_client_current

- attempted: `False`
- status: `not_run_in_path_b_isolation_pass`
- reason: `PATH B exact reproduction must be established before repo-client correction testing.`

## Next Action

PATH B exact reproduction succeeded. Next compare repo AdobeAPIClient against this exact request shape.
