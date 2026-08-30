# Adobe Access Waiting Status

## What Works

- credential loading
- client_credentials token acquisition
- live API smoke infrastructure
- large live-run guard protection
- local deterministic SQL_FIRST_API_VERIFY pipeline

## What Is Blocked

- Live success count: `0`
- Usable live API payload evidence: `0`
- Full live eval allowed: `False`
- Full live generated prompt suite allowed: `False`

## Why This Is Likely External Adobe Access

- credential loading and client-credentials token acquisition pass locally
- safe GET smoke infrastructure executes real Adobe requests
- endpoint failures are grouped as permission/scope, sandbox/environment, unresolved path evidence, or service/server issues
- no safe GET endpoint has returned live payload evidence yet

## What External Access Is Needed

- Adobe Organization access
- workshop sandbox access
- AEP read permissions for schemas, datasets, audiences/segments, merge policies, flow service, and audit events

## What Command To Run After Permission Is Granted

`python3 scripts/run_post_permission_live_api_verification.py`

Immediate smoke rerun: `python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get`

## Current Guard Status

- Guard decision: `allowed_not_live_mode`
- Reason: `not_live_mode`
- Live success count: `0`
- Full live eval allowed: `False`
- Full generated prompt suite allowed: `False`

## What Local Work Was Completed While Waiting

- Local 250-prompt diagnostic completed: `250` / `250`
- Runtime pass count: `250`
- Runtime fail count: `0`
- Official score claim: `False`
- No safe deterministic improvement applied: `True`

## Recommended Next Human Review

- Category: `missing_count_or_name_advisory / segment_audience`
- Why: Largest reviewed high-value category; inspect examples before any runtime change.
- Report: `outputs/reports/local_gap_manual_review.md`
- Can be fixed before Adobe access: `False`
