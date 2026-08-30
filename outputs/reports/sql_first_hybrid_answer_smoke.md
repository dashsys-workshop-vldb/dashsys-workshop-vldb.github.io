# SQL First Hybrid Answer Smoke

No promotion recommendation.

## hybrid_answer_count_smoke
- Intent/mode: `COUNT` / `CANONICAL_DATA`
- Selected source: `HYBRID_CANONICAL_DATA`
- SQL/API/tool calls: `1` / `1` / `2`
- Verifier ok: `True`
- Unsupported claims: `0`
- Final answer: There are 74 schema records in the local snapshot.

## hybrid_answer_date_smoke
- Intent/mode: `STATUS` / `CANONICAL_DATA`
- Selected source: `LEGACY_SAFE_RENDERER`
- SQL/API/tool calls: `1` / `1` / `2`
- Verifier ok: `True`
- Unsupported claims: `0`
- Final answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and live API verification was not executed because Adobe credentials are unavailable.

## hybrid_answer_list_status_smoke
- Intent/mode: `STATUS` / `CANONICAL_DATA`
- Selected source: `LEGACY_SAFE_RENDERER`
- SQL/API/tool calls: `1` / `1` / `2`
- Verifier ok: `True`
- Unsupported claims: `0`
- Final answer: There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). Live API verification was not executed because Adobe credentials are unavailable.

## hybrid_answer_concept_smoke
- Intent/mode: `CONCEPT` / `LLM_CONCEPT`
- Selected source: `HYBRID_LLM_CONCEPT`
- SQL/API/tool calls: `1` / `1` / `2`
- Verifier ok: `True`
- Unsupported claims: `0`
- Final answer: A schema defines the structure, fields, and expected shape of data.
