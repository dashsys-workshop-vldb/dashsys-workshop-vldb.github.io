# LLM Semantic Routing Helper Shadow Eval

Diagnostic only. This report does not compute official strict score and does not promote runtime behavior.

- Status: `complete`
- Feature flag default: `off`
- Shadow-only: `True`
- Backend/model: `[REDACTED]`
- Backend type: `openai_sdk`
- SDK path used: `True`
- Total prompts: `50`
- Helper eligible prompts: `39`
- Helper called prompts: `39`
- Valid helper outputs: `39`
- Rejected helper outputs: `0`
- Normalization actions count: `1`
- Synonym mappings coerced count: `0`
- Domain aliases applied count: `1`
- Recommendation: `keep_shadow_only`

## Rejection Reasons

- `none`: `0`

## Normalization Actions

- `domain_alias:audit->observability`: `1`

## Examples

- Valid hint examples shown: `3`
- `example_003`: domain=`journey_campaign`, route=`SQL_ONLY`, intent=`LIST`, actions=`[]`
- `example_004`: domain=`segment_audience`, route=`SQL_ONLY`, intent=`LIST`, actions=`[]`
- `example_005`: domain=`destination_dataflow`, route=`SQL_THEN_API`, intent=`DETAIL`, actions=`[]`
- Rejected hint examples shown: `0`
