
# Research Generalized V2 Organizer 35

| Strategy | Final | Correctness | SQL | API | Answer | Tool Calls | Runtime | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SQL_FIRST_API_VERIFY | 0.6562 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 1.4571 | 1.1843 | 791.3429 |
| ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 | 0.6348 | 0.6644 | 0.9333 | 0.9591 | 0.2853 | 1.4 | 0.8315 | 1110.6571 |

Helped/hurt/neutral: 4/30/1
Severe regressions: 6
API_REQUIRED underuse proxy count: 2
No-tool false positives: 0
Unsupported claims: 0
Progressive checkpoint coverage: 100.0%
Hybrid answer checkpoint coverage: 100.0%

Answer intent counts: `{'STATUS': 4, 'LIST': 18, 'COUNT': 11, 'ERROR_CAVEAT': 2}`
Answer mode counts: `{'CANONICAL_DATA': 33, 'CANONICAL_CAVEAT': 2}`
Selected answer source counts: `{'LEGACY_SAFE_RENDERER': 24, 'DETERMINISTIC_FALLBACK': 9, 'HYBRID_CANONICAL_CAVEAT': 1, 'HYBRID_CANONICAL_DATA': 1}`
