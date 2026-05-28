# SQL_FIRST LLM Answer Empty Fix

1. Root cause: the default-selected OpenRouter answer backend returns auth/401-class empty responses, while a configured OpenAI SDK backend can return content.
2. Failure category counts before fix: `{'empty_llm_answer': 35}`
3. Non-empty LLM generations after fix: `35/35`
4. Generator category counts after fix: `{'NONE': 35}`
5. Primary backend category counts: `{'LLM_BACKEND_AUTH_FAILED': 35}`
6. Successful fallback provider counts: `{'openai': 35}`
7. Prior high-scoring path status: `runtime_payload_clean_but_score_inflated_by_empty_answer_evaluator_bug`
8. Fix applied:
- Normalized LLM answer responses from choices[0].message.content, output_text, content blocks, complete/chat/complete_json/generate_messages.
- Added generator_category/debug fields for backend unavailable, backend auth failure, rate limit/quota/model/network/provider failures, raw empty content, malformed content, and exceptions.
- Added shared LLM client error_category classification while preserving redacted error text only.
- Mapped auth_or_401 provider failures to LLM_BACKEND_AUTH_FAILED in answer generation reports.
- Added answer-generator fallback across configured SDK providers after primary backend failure.
- Added strict answer scorer guard so empty generated answers receive 0 answer credit.

## Smoke Results

| query_id | generated | chars | primary category | fallback provider | selected source | answer fallback | SQL | API |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: |
| `debug_llm_answer_inactive_journeys` | True | 367 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | True | 1 | 1 |
| `debug_llm_answer_birthday_published` | True | 196 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | True | 1 | 1 |
| `debug_llm_answer_local_schema_count` | True | 156 | LLM_BACKEND_AUTH_FAILED | openai | DETERMINISTIC_FALLBACK | True | 1 | 1 |

## Organizer 35

| Strategy | Final | Correctness | SQL | API | Answer | SQL calls | API calls | Avg tool calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `SQL_FIRST_API_VERIFY` | 0.6579 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 15 | 36 | 1.4571 |
| `SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER` | 0.6517 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 15 | 36 | 1.4571 |

- LLM non-empty generation: `35/35`
- Backend fallback used: `35/35`
- Selected answer sources: `{'LEGACY_SAFE_RENDERER': 35}`
- Answer lift reproduced: `False`
- Reason: generated content is now non-empty, but the runtime answer selector still chooses legacy-safe answers for all rows.
- SQL/API call deltas: `0/0`
- Unsupported claims: `0`
- SDK usage audit: `runtime_llm_direct_http_hits=0`
- check_submission_ready: `ok=true`
- git diff --check: `ok=true`
- Packaged default unchanged: `SQL_FIRST_API_VERIFY`
- No promotion recommendation was made.
