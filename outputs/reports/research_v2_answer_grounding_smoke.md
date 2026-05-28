# Research V2 Answer Grounding Smoke

Generated: 2026-05-28T16:02:55.924591+00:00

| Query | Entry | SQL | API | Broad | Intent / Mode | Source | Final answer |
|---|---:|---:|---:|---|---|---|---|
| `research_v2_concept_list_reasons` | LLM_DIRECT | 0 | 0 | CONCEPTUAL_BROAD | CONCEPT / LLM_CONCEPT | HYBRID_LLM_CONCEPT | Schemas matter because they make data structure explicit, keep records consistent, and help systems validate and interpret data. |
| `research_v2_meta_list_schemas` | LLM_DIRECT | 0 | 0 | CONCEPTUAL_BROAD | CONCEPT / LLM_CONCEPT | HYBRID_LLM_CONCEPT | In this phrase, list means to enumerate or show the requested items. |
| `research_v2_inactive_journeys` | EVIDENCE_PIPELINE | 1 | 1 | NOT_BROAD | STATUS / CANONICAL_DATA | LEGACY_SAFE_RENDERER | There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). Live API verification was not executed because Adobe credentials are unavailable. |
| `research_v2_local_schema_count` | EVIDENCE_PIPELINE | 1 | 0 | NOT_BROAD | COUNT / CANONICAL_DATA | HYBRID_CANONICAL_DATA | There are 74 schema records in the local snapshot. |
| `research_v2_live_schema_count` | EVIDENCE_PIPELINE | 1 | 1 | DATA_BROAD | COUNT / LEGACY_FIRST_DATA | HYBRID_CANONICAL_DATA | Local snapshot schemas count: 74. API unavailable/error; cannot verify live state. Live API verification was not executed because Adobe credentials are unavailable. |
| `research_v2_mixed_inactive_journey` | EVIDENCE_PIPELINE | 1 | 1 | MIXED_BROAD | MIXED / HYBRID_MIXED | HYBRID_MIXED | An inactive journey is a journey that is not currently active or running. Journeys: Birthday Message (updated); Gold Tier Welcome Email (created). API unavailable/error; cannot verify live state. Live API verification was not executed because Adobe credentials are unavailable. |

All six rows include research/progressive checkpoints. Concept and meta-language rows used zero tools. Data-like rows entered evidence collection or preserved API/caveat behavior.

No promotion recommendation.
