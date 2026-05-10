# Diagnostic Prompt Suite Run

Diagnostic prompt coverage only; not official strict score.

- Strategy: `SQL_FIRST_API_VERIFY`
- LLM runtime used: `False`
- LLM semantic router shadow enabled: `False`
- Total prompts in suite: `250`
- Executed prompts: `50`
- Passed runtime count: `50`
- Failed runtime count: `0`
- Validation failure count: `0`
- Dry-run API count: `50`

## Route Distribution

- `API_ONLY`: `5`
- `SQL_ONLY`: `27`
- `SQL_THEN_API`: `18`

## Top Failure Categories

- `none`: `0`

## Recommended Future Improvement Areas

- Review diagnostic route mismatches for prompt-router and query-analysis coverage.
- Keep dry-run wording concise and avoid fabricated live API payloads.

Generated prompts are not packaged into final submission and are not used by official strict eval.
