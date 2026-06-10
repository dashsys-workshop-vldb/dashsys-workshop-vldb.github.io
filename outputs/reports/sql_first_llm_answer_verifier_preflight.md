# SQL_FIRST_API_VERIFY + LLM Answer Verifier Preflight

- Current default strategy: `SQL_FIRST_API_VERIFY`
- SQL_FIRST_API_VERIFY exists: `True`
- New strategy exists before patch: `False`
- Evidence-grounded LLM answer generator available: `True`
- Final answer verifier available: `True`
- AnswerSlots/EvidenceBus available: `True`
- check_submission_ready ok: `True`
- Expected packaged strategy: `SQL_FIRST_API_VERIFY`
- Query output count: `73`
- Git status lines: `6470`

## Provided Prior Ablation Numbers

| Strategy | Final | Correctness | SQL | API | Answer | SQL calls | API calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| `SQL_FIRST_API_VERIFY` | 0.6578 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 15 | 36 |
| `ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER` | 0.8884 | 0.9172 | 0.9333 | 0.9791 | 0.85 | 15 | 36 |

No runtime/default changes were made before this report.
