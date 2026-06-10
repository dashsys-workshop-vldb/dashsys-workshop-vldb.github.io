# Live API External Blockers

Current normal runtime has live_success endpoints and usable live API evidence. Remaining blockers are endpoint-specific; historical HTTP 500 results are old misaligned-runtime evidence only.

- Full live strict eval blocked: `False`
- Full generated prompt suite blocked: `False`

## Likely Adobe permission/scope setup

- Affected endpoints: `[]`
- Why code should not blindly change runtime: Token acquisition works, but the data endpoint rejects access. Changing runtime code would hide an Adobe access problem.
- What to verify: Verify Adobe product access, API key entitlement, and OAuth scopes for these endpoint families.

Rerun commands:

## Likely sandbox/environment setup

- Affected endpoints: `[]`
- Why code should not blindly change runtime: Responses point to sandbox, tenant, org, or environment scope. Runtime should not guess a different sandbox or org.
- What to verify: Verify the sandbox name, org/project access, and whether the selected sandbox has these services enabled.

Rerun commands:

## Unresolved endpoint/path evidence with no proven code fix

- Affected endpoints: `[]`
- Why code should not blindly change runtime: Endpoint path probes did not return a successful safe GET candidate, so a blind catalog edit would be speculative.
- What to verify: Review endpoint path diagnosis and rerun focused smoke after external checks; do not change catalog paths without a successful safe GET candidate.

Rerun commands:

## Required safe request shape mismatch

- Affected endpoints: `[]`
- Why code should not blindly change runtime: This points to endpoint-specific request shape, not an AdobeAPIClient token/auth defect.
- What to verify: Run the isolated request-shape trial and apply only if the focused safe GET succeeds.

Rerun commands:

## Likely Adobe service/server issue

- Affected endpoints: `[]`
- Why code should not blindly change runtime: The response shape looks like a server/service failure rather than actionable local code evidence.
- What to verify: Rerun later and check Adobe service status or request logs for the endpoint.

Rerun commands:
