# Workshop Requirement Audit

- Official source: https://dashsys-workshop-vldb.github.io/systems.html
- Overall status: `pass`
- Critical failures: `0`
- Warnings: `0`

## Critical Failures

- None.

## Warnings

- None.

## Official Requirement Mapping

- **execute_sql(sql)** `pass` - Tool execute_sql(sql) must execute database SQL. Evidence: `dashagent/db.py`, `dashagent/validators.py`, `tests/test_db.py`
- **call_api(method, url, params, headers)** `pass` - Tool call_api(method, url, params, headers) must make sandbox REST API calls. Evidence: `dashagent/api_client.py`, `dashagent/validators.py`, `dashagent/endpoint_catalog.py`
- **additional_deliverables** `pass` - Submit a system prompt template and source-code archive. Evidence: `outputs/final_submission/system_prompt_template.txt`, `outputs/final_submission/source_code.zip`, `outputs/final_submission_manifest.json`
- **per_query_deliverables** `pass` - For each query submit metadata.json, filled_system_prompt.txt, and trajectory.json. Evidence: `outputs/final_submission/query_###/metadata.json`, `outputs/final_submission/query_###/filled_system_prompt.txt`, `outputs/final_submission/query_###/trajectory.json`
- **evaluation_dimensions** `pass` - Evaluation covers SQL/API/response correctness plus turns/tool calls/tokens/wall time and trajectory reproducibility. Evidence: `outputs/eval_results_strict.json`, `outputs/hidden_style_eval.json`, `scripts/check_submission_ready.py`
- **harness_model_generality** `pass` - Organizer may run the system prompt with Claude Agent SDK or OpenAI Agents SDK and any model. Evidence: `prompts/system_prompt_template.txt`, `dashagent/llm_client.py`, `outputs/reports/sdk_usage_audit.json`
- **diagnostic_prompt_suite_separation** `pass` - Public examples are illustration/validation only; broader diagnostic prompts must not become official scoring data. Evidence: `data/generated_prompt_suite.json`, `outputs/reports/generated_prompt_suite_summary.json`, `scripts/package_query_outputs.py`
- **documentation_alignment** `pass` - Submission should be easy to verify and describe architecture, prompting strategy, evaluation, and safe operation. Evidence: `README.md`, `AGENTS.md`, `outputs/reports/report_index.md`

## Audit Items

| Requirement | Status | Evidence | Explanation |
|---|---:|---|---|
| Implement execute_sql(sql) and keep SQL read-only. | `pass` | `dashagent/db.py`<br/>`dashagent/validators.py` | execute_sql exists and read-only checks block destructive SQL. |
| Implement call_api(method, url, params, headers) with endpoint/API validation. | `pass` | `dashagent/api_client.py`<br/>`dashagent/validators.py`<br/>`dashagent/endpoint_catalog.py` | call_api exists and APIValidator/endpoint catalog are present. |
| Submit system_prompt_template.txt, source_code.zip, final_submission_manifest.json, and final_submission query outputs. | `pass` | `outputs/final_submission`<br/>`outputs/final_submission/system_prompt_template.txt`<br/>`outputs/final_submission/source_code.zip`<br/>`outputs/final_submission_manifest.json` | All top-level final submission deliverables exist. |
| Keep packaged default strategy unchanged as SQL_FIRST_API_VERIFY. | `pass` | `outputs/final_submission_manifest.json` | preferred_strategy=SQL_FIRST_API_VERIFY |
| Each packaged query directory contains metadata.json, filled_system_prompt.txt, and trajectory.json. | `pass` | `outputs/final_submission` | Checked 73 query directories; missing file records=0. |
| Trajectory JSON is parseable, reproducible, and records query, answer, tool count, tokens, runtime, and SQL/API actions. | `pass` | `outputs/final_submission` | Checked 73 trajectories; invalid=0, missing_fields=0, missing_action_records=0. |
| Final submission and trajectory artifacts must not leak secrets. | `pass` | `outputs/final_submission` | check_submission_ready secret scan passed. |
| source_code.zip must include source code without .env.local, caches, outputs, generated diagnostic data, or secrets. | `pass` | `outputs/final_submission/source_code.zip` | zip_entries=225, forbidden_entries=0, secret_hits=0 |
| Diagnostic prompts, diagnostic outputs, LLM raw artifacts, caches, and stale duplicate files must not be packaged into final_submission. | `pass` | `outputs/final_submission` | No diagnostic or stale output contamination found. |
| Reports cover SQL correctness, API correctness, response correctness, tool calls, tokens, wall time, hidden-style robustness, and readiness. | `pass` | `outputs/eval_results_strict.json`<br/>`outputs/hidden_style_eval.json`<br/>`outputs/winner_readiness_report.json`<br/>`outputs/final_submission_manifest.json` | Strict/component metrics, hidden-style report, and readiness checks are available. |
| System prompt should generalize across Claude/OpenAI-style harnesses and avoid public/gold/model-specific runtime assumptions. | `pass` | `prompts/system_prompt_template.txt`<br/>`outputs/final_submission/system_prompt_template.txt` | Prompt is tool-grounded and model-generic. |
| All LLM/model provider calls must use get_llm_client() or LLMClient SDK paths; direct runtime HTTP hits must be zero. | `pass` | `outputs/reports/sdk_usage_audit.json` | runtime_llm_direct_http_hits=0 |
| Generated prompt suite is diagnostic-only, not official scoring data, and excluded from final submission. | `pass` | `data/generated_prompt_suite.json`<br/>`scripts/run_dev_eval.py`<br/>`scripts/package_query_outputs.py` | prompts=250, diagnostic_flags_ok=True, official_eval_separate=True, packaging_excluded=True |
| README.md and AGENTS.md explain official tools, deliverables, default strategy, validation, diagnostic separation, SDK LLM rule, and no hardcoding/gold-label rules. | `pass` | `README.md`<br/>`AGENTS.md` | Documentation contains required alignment guidance. |
| report_index.md/json links workshop_requirement_audit.md under Workshop Requirement Alignment. | `pass` | `outputs/reports/report_index.md`<br/>`outputs/reports/report_index.json` | markdown_link=True, json_link=True |

## Assumptions

- `original_query` satisfies the official user-query trace requirement when `query` is absent.
- Diagnostic prompt labels are coverage hints only and are not official gold labels.
- The SDK-only rule applies to LLM/model provider calls; Adobe REST API execution stays on the existing API client path.
