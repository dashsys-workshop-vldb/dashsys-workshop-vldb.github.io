# Context7 Code Alignment Audit

- Status: `complete`
- Documentation grounded: `True`
- Runtime change recommended: `False`

## OpenAI SDK

- Status: `aligned`
- Findings:
  - Uses OpenAI SDK client object for chat completions.
  - Normalizes tool_calls and JSON argument strings defensively.
  - Reads usage metadata from model-dumped SDK response without assuming token fields are present.
  - Runtime direct LLM HTTP hits: `0`.
- Files:
  - `dashagent/llm_client.py`
  - `scripts/check_llm_sdk_backend.py`

## Anthropic SDK

- Status: `aligned`
- Findings:
  - Uses Anthropic SDK messages.create path instead of direct HTTP.
  - Converts OpenAI-style tools into Anthropic name/description/input_schema shape.
  - Converts tool_use blocks back to the common internal tool-call shape.
  - Normalizes input/output token usage into total_tokens defensively.
- Files:
  - `dashagent/llm_client.py`

## Adobe API Auth And Headers

- Status: `blocked_by_adobe_permission`
- Findings:
  - Env readiness uses supported primary names and aliases without value-bearing report output.
  - default_headers builds Authorization, x-api-key, x-gw-ims-org-id, and x-sandbox-name when constructible.
  - Token acquisition failures return structured non-dry-run API evidence.
  - Safe smoke/trial paths remain GET-only for Adobe data endpoints; IMS token request is the only OAuth POST.
  - Current live data success remains blocked by Adobe endpoint-level permission/sandbox/path/service outcomes, not by credential construction.
- Files:
  - `dashagent/api_client.py`
  - `dashagent/adobe_env.py`
  - `dashagent/api_outcome_classifier.py`
  - `scripts/run_live_api_readiness_smoke.py`
  - `scripts/run_post_permission_live_api_verification.py`

## DuckDB And SQLGlot SQL Safety

- Status: `aligned`
- Findings:
  - DuckDB execute path is wrapped by read-only SQL checks before execution.
  - Multiple statements and destructive/environment-changing commands are blocked before DuckDB execution.
  - SQLGlot parse_one uses the DuckDB dialect for AST summaries and destructive-expression detection.
  - SQL validation reports parse warnings safely instead of crashing the executor.
- Files:
  - `dashagent/db.py`
  - `dashagent/sql_ast_tools.py`
  - `dashagent/validators.py`

## Pydantic / SDK Model Serialization

- Status: `aligned`
- Findings:
  - Repo does not define first-party Pydantic models in runtime paths.
  - SDK responses are serialized through model_dump when present, then dict/json fallbacks.
  - Generated reports call json.dumps with default=str for non-JSON-native metadata.
- Files:
  - `dashagent/llm_client.py`
  - `scripts/generate_consolidated_reports.py`

## CLI And Test Harness

- Status: `aligned`
- Findings:
  - Large live-run override is an explicit CLI flag, not an implicit env toggle.
  - Tests use isolated tmp_path and monkeypatch patterns for report and environment coverage.
  - Diagnostics are marked diagnostic-only and do not overwrite official strict artifacts under guarded override.
- Files:
  - `scripts/run_dev_eval.py`
  - `tests`
