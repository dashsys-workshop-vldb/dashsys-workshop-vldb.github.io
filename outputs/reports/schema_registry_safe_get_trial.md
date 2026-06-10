# Schema Registry Safe GET Trial

GET-only isolated Schema Registry request-shape trial. No runtime change is applied by this report.

## Variant Results

| variant | method | path | params | accept | status | outcome | json_parse_ok | usable_payload_present | parser_status | official_shape |
|---|---|---|---|---|---:|---|---|---|---|---|
| `current_baseline` | `GET` | `/data/foundation/schemaregistry/tenant/schemas` | `{'limit': 25}` | `None` | 400 | `api_error` | `True` | `False` | `pass` | `False` |
| `A_current_path_xed_id_accept` | `GET` | `/data/foundation/schemaregistry/tenant/schemas` | `{'limit': 25}` | `application/vnd.adobe.xed-id+json` | 200 | `live_empty` | `True` | `False` | `pass` | `True` |
| `B_official_tenant_xed_id_accept` | `GET` | `/data/foundation/schemaregistry/tenant/schemas` | `{}` | `application/vnd.adobe.xed-id+json` | 200 | `live_empty` | `True` | `False` | `pass` | `True` |
| `C_official_global_xed_id_accept` | `GET` | `/data/foundation/schemaregistry/global/schemas` | `{}` | `application/vnd.adobe.xed-id+json` | 200 | `live_empty` | `True` | `False` | `pass` | `True` |

## Decision
- apply_fix: `True`
- root_cause: `missing_required_accept_header`
- chosen_variant_id: `A_current_path_xed_id_accept`

## Parser Check `A_current_path_xed_id_accept`
- schema_registry_parser_status: `pass`
- schema_registry_usable_evidence: `False`
- schema_registry_answer_usage_ready: `False`
- parser_fix_required: `False`

## Parser Check `B_official_tenant_xed_id_accept`
- schema_registry_parser_status: `pass`
- schema_registry_usable_evidence: `False`
- schema_registry_answer_usage_ready: `False`
- parser_fix_required: `False`

## Parser Check `C_official_global_xed_id_accept`
- schema_registry_parser_status: `pass`
- schema_registry_usable_evidence: `False`
- schema_registry_answer_usage_ready: `False`
- parser_fix_required: `False`
