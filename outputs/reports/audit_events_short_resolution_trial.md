# Audit Events Short Resolution Trial

- Diagnostic only: `true`
- Official score claim: `false`

## Variants

### current_baseline
- endpoint_id: `audit_events_short`
- method/path: `GET /audit/events`
- params: `{"limit": 50}`
- status/outcome: `404` / `endpoint_path_issue`
- parser_status: `pass`
- fix_allowed: `False`

### canonical_existing_audit_events
- endpoint_id: `audit_events`
- method/path: `GET /data/foundation/audit/events`
- params: `{"limit": 20}`
- status/outcome: `200` / `live_empty`
- parser_status: `pass`
- fix_allowed: `False`

### audit_events_short_canonical_shape
- endpoint_id: `audit_events_short`
- method/path: `GET /data/foundation/audit/events`
- params: `{"limit": 50}`
- status/outcome: `200` / `live_empty`
- parser_status: `pass`
- fix_allowed: `True`

## Decision
- resolution_state: `safely_aliased_to_proven_canonical_endpoint`
- apply_fix: `True`
- chosen_variant_id: `audit_events_short_canonical_shape`
