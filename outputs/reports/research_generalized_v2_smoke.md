# Research Generalized V2 Smoke

| Query ID | Entry | SQL | API | Intent | Mode | Source | Unsupported | Final Answer |
|---|---|---:|---:|---|---|---|---:|---|
| `research_v2_concept_list_reasons` | LLM_DIRECT | 0 | 0 | None | None | None | 0 | A schema is a blueprint for how data is structured: it defines fields, types, and constraints so systems can interpret records consistently. |
| `research_v2_meta_list_schemas` | LLM_DIRECT | 0 | 0 | None | None | None | 0 | In that phrase, list means to return or enumerate matching items; this is a wording question, not a request to query schema records. |
| `research_v2_inactive_journeys` | EVIDENCE_PIPELINE | 1 | 1 | STATUS | CANONICAL_DATA | LEGACY_SAFE_RENDERER | 0 | There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). Live API verification was not executed because Adobe credentials are unavailable. |
| `research_v2_local_schema_count` | EVIDENCE_PIPELINE | 1 | 0 | COUNT | CANONICAL_DATA | HYBRID_CANONICAL_DATA | 0 | There are 74 schema records in the local snapshot. |
| `research_v2_live_schema_count` | EVIDENCE_PIPELINE | 1 | 1 | COUNT | CANONICAL_DATA | LEGACY_SAFE_RENDERER | 0 | You have 74 schemas. Live API verification was not executed because Adobe credentials are unavailable. |
| `research_v2_mixed_inactive_journey` | EVIDENCE_PIPELINE | 1 | 1 | MIXED | HYBRID_MIXED | HYBRID_MIXED | 0 | An inactive journey is a journey that is not currently active or running. Journeys: Birthday Message (updated); Gold Tier Welcome Email (created). API unavailable/error; cannot verify live state. Live API verification was not executed because Adobe credentials are unavailable. |
