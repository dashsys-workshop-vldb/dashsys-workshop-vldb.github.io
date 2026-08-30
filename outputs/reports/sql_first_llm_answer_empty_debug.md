# SQL_FIRST LLM Answer Empty Debug

- Rows inspected: `35`
- Non-empty LLM generations: `35`
- Generator category counts: `{'NONE': 35}`
- Primary backend category counts: `{'LLM_BACKEND_AUTH_FAILED': 35}`
- Primary backend error category counts: `{'auth_or_401': 35}`
- Successful fallback provider counts: `{'openai': 35}`
- Selected answer source counts: `{'LEGACY_SAFE_RENDERER': 35}`
- Root cause: default-selected OpenRouter failed auth; SDK fallback to OpenAI generated non-empty answer content. No credential values are recorded.

| query_id | generated chars | primary category | fallback provider | selected source | answer fallback |
| --- | ---: | --- | --- | --- | ---: |
| `example_000` | 105 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | True |
| `example_001` | 132 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_002` | 179 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_003` | 58 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_004` | 277 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | True |
| `example_005` | 126 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_006` | 9 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_007` | 82 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | True |
| `example_008` | 43 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | True |
| `example_009` | 54 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_010` | 9 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_011` | 10 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_012` | 70 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_013` | 146 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_014` | 95 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_015` | 9 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_016` | 185 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_017` | 207 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | True |
| `example_018` | 65 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_019` | 142 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_020` | 9 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_021` | 146 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_022` | 10 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_023` | 277 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_024` | 277 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_025` | 197 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_026` | 9 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_027` | 190 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_028` | 85 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | True |
| `example_029` | 10 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_030` | 58 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_031` | 172 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | True |
| `example_032` | 91 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_033` | 9 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
| `example_034` | 9 | LLM_BACKEND_AUTH_FAILED | openai | LEGACY_SAFE_RENDERER | False |
