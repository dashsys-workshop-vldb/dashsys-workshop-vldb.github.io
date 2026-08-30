# schemas_short Safe GET Trial

- Diagnostic only: `true`
- Official score claim: `false`

## Variant Results

### current_baseline
- intended semantics: current schemas_short shorthand schema-list request
- method/path: `GET /schemas`
- params: `{"limit": 25}`
- header names: `[]`
- Accept media type: `None`
- status/outcome: `404` / `endpoint_path_issue`
- json_parse_ok: `True`
- parser_status: `pass`
- live_success/live_empty: `False` / `False`
- fix_allowed: `False`

### A_current_path_xed_id_accept
- intended semantics: current schemas_short path plus Schema Registry list Accept header
- method/path: `GET /schemas`
- params: `{"limit": 25}`
- header names: `['Accept']`
- Accept media type: `application/vnd.adobe.xed-id+json`
- status/outcome: `404` / `endpoint_path_issue`
- json_parse_ok: `True`
- parser_status: `pass`
- live_success/live_empty: `False` / `False`
- fix_allowed: `False`

### B_canonical_tenant_xed_id_accept
- intended semantics: canonical tenant schema list alias for schemas_short
- method/path: `GET /data/foundation/schemaregistry/tenant/schemas`
- params: `{}`
- header names: `['Accept']`
- Accept media type: `application/vnd.adobe.xed-id+json`
- status/outcome: `200` / `live_empty`
- json_parse_ok: `True`
- parser_status: `pass`
- live_success/live_empty: `False` / `True`
- fix_allowed: `True`

### C_canonical_global_xed_id_accept
- intended semantics: diagnostic global schema list only; not a tenant alias replacement
- method/path: `GET /data/foundation/schemaregistry/global/schemas`
- params: `{}`
- header names: `['Accept']`
- Accept media type: `application/vnd.adobe.xed-id+json`
- status/outcome: `200` / `live_empty`
- json_parse_ok: `True`
- parser_status: `pass`
- live_success/live_empty: `False` / `True`
- fix_allowed: `False`

## Fix Decision
- apply_fix: `True`
- root_cause: `shorthand_endpoint_path_mismatch`
- chosen_variant_id: `B_canonical_tenant_xed_id_accept`
- fix_scope: `schemas_short_alias_to_canonical_tenant_schema_list_with_endpoint_specific_accept`
