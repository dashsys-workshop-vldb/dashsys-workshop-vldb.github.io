# API Endpoint Selection Gap Analysis

This diagnostic looks for endpoint-family selection issues and optional API noise without changing endpoint catalog paths or runtime ranking.

- Gap count: `152`
- Gap types: `{'less_useful_or_error_endpoint_selected': 138, 'optional_api_call_when_sql_complete': 14}`
- API outcomes: `{'api_error': 139, 'live_success': 23}`

## Trial Variants

- `live_endpoint_health_ranking`: affected rows `138`, estimated API calls saved `0`
- `parser_supported_endpoint_boost`: affected rows `138`, estimated API calls saved `0`
- `optional_api_suppression_when_sql_complete`: affected rows `14`, estimated API calls saved `14`
- `api_family_answer_intent_alignment`: affected rows `138`, estimated API calls saved `0`
