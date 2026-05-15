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

## What External Access Is Needed

- Adobe Organization access
- workshop sandbox access
- AEP read permissions for schemas, datasets, audiences/segments, merge policies, flow service, and audit events

## What Command To Run After Permission Is Granted

`python3 scripts/run_post_permission_live_api_verification.py`
