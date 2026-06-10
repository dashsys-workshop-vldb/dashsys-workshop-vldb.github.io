# Unified Tags Resolution Trial

- Diagnostic only: `true`
- Official score claim: `false`

## Variants

### unified_tags / current_baseline
- method/path: `GET /unifiedtags/tags`
- params: `{"limit": 25}`
- status/outcome: `404` / `endpoint_path_issue`
- parser_status: `pass`
- fix_allowed: `False`

### unified_tags / documented_experience_tags
- method/path: `GET https://experience.adobe.io/unifiedtags/tags`
- params: `{"limit": 25}`
- status/outcome: `200` / `live_success`
- parser_status: `pass`
- fix_allowed: `True`

### unified_tag_categories / current_baseline
- method/path: `GET /unifiedtags/tagCategory`
- params: `{"limit": 100}`
- status/outcome: `404` / `endpoint_path_issue`
- parser_status: `pass`
- fix_allowed: `False`

### unified_tag_categories / documented_experience_tag_categories
- method/path: `GET https://experience.adobe.io/unifiedtags/tagCategory`
- params: `{"limit": 100}`
- status/outcome: `200` / `live_success`
- parser_status: `pass`
- fix_allowed: `True`

## Decisions
- `unified_tags`: `fixed_with_proven_live_request_shape` via `documented_experience_tags`
- `unified_tag_categories`: `fixed_with_proven_live_request_shape` via `documented_experience_tag_categories`
