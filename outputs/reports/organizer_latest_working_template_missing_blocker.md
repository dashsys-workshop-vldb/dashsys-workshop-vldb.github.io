# Organizer Latest Working Template Missing Blocker

Generated at: `2026-05-24T17:50:02Z`

Status: `superseded_template_provided`

This initial blocker is superseded. The user later provided the latest organizer code template in chat. Per the live API correction rule, no runtime code, endpoint catalog path, scope, header, parameter, organization context, sandbox mapping, SQL strategy, or final-submission artifact was changed until the latest template could be tested locally.

## Historical Baseline Preserved

The previous organizer UPS audiences smoke evidence was preserved as historical baseline:

- `outputs/reports/baselines/organizer_adobe_ups_audiences_old_template_500.md`
- `outputs/reports/baselines/organizer_adobe_ups_audiences_old_template_500.json`
- `outputs/reports/baselines/organizer_adobe_ups_audiences_old_template_500_evidence_package.md`
- `outputs/reports/baselines/organizer_adobe_ups_audiences_old_template_500_evidence_package.json`

Baseline summary:

- Token status code: `200`
- Token acquisition ok: `true`
- Data endpoint method/path: `GET /data/core/ups/audiences`
- Safe params: `{"limit": 5}`
- Previous direct status: `500`
- Previous repo-client status: `500`
- Previous comparison result: `both_same_failure`

## Superseded Input Requirement

The snippet requirement has been satisfied. The non-secret request shape now tested is:

- token URL host and path
- grant type
- scope string or normalized scope list
- data base URL host
- data endpoint method
- data endpoint path
- safe query params
- required header names
- which placeholders map to organization context
- which placeholders map to sandbox context

Credential values remain omitted from reports.

## Current Blocker

Full live strict eval and full live generated-prompt diagnostics remain `BLOCKED` for this pass. The current issue is that the latest-template local reproduction returned HTTP `500`, not `live_success`. See `outputs/reports/organizer_latest_working_template_smoke.json` and `outputs/reports/live_api_post_fix_go_no_go.json`.
