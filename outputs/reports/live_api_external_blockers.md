# Live API External Blockers

Adobe credentials and token acquisition work, but live data endpoints have not returned usable payload evidence. Treat current blockers as external setup or unresolved endpoint evidence until at least one safe GET endpoint returns live_success.

- Full live strict eval blocked: `True`
- Full generated prompt suite blocked: `True`

## Likely Adobe permission/scope setup

- Affected endpoints: `['ups_audiences', 'segment_definitions', 'merge_policies']`
- Why code should not blindly change runtime: Token acquisition works, but the data endpoint rejects access. Changing runtime code would hide an Adobe access problem.
- What to verify: Verify Adobe product access, API key entitlement, and OAuth scopes for these endpoint families.

Rerun commands:
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id ups_audiences`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id segment_definitions`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id merge_policies`

## Likely sandbox/environment setup

- Affected endpoints: `['flowservice_flows', 'flowservice_runs', 'schema_registry_schemas', 'audit_events']`
- Why code should not blindly change runtime: Responses point to sandbox, tenant, org, or environment scope. Runtime should not guess a different sandbox or org.
- What to verify: Verify the sandbox name, org/project access, and whether the selected sandbox has these services enabled.

Rerun commands:
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id flowservice_flows`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id flowservice_runs`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id schema_registry_schemas`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id audit_events`

## Unresolved endpoint/path evidence with no proven code fix

- Affected endpoints: `['catalog_datasets', 'unified_tags', 'catalog_batches', 'schemas_short']`
- Why code should not blindly change runtime: Endpoint path probes did not return a successful safe GET candidate, so a blind catalog edit would be speculative.
- What to verify: Review endpoint path diagnosis and rerun focused smoke after external checks; do not change catalog paths without a successful safe GET candidate.

Rerun commands:
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id catalog_datasets`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id unified_tags`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id catalog_batches`
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id schemas_short`

## Likely Adobe service/server issue

- Affected endpoints: `['journey_list']`
- Why code should not blindly change runtime: The response shape looks like a server/service failure rather than actionable local code evidence.
- What to verify: Rerun later and check Adobe service status or request logs for the endpoint.

Rerun commands:
- `python3 scripts/run_live_api_readiness_smoke.py --endpoint-id journey_list`
