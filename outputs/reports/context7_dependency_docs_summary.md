# Context7 Dependency Docs Summary

This report stores short findings only. Raw Context7 documentation output is not stored.

- Dependency count: `8`
- Context7 found count: `8`
- Raw docs stored: `False`

## OpenAI Python SDK

- Context7 library ID: `/openai/openai-python`
- Result: `found`
- Query: `chat completions tool calling usage token usage fields`
- Risk: `medium`
- Code audit needed: `True`
- Findings:
  - Chat completions are invoked through the SDK client method, with tools supplied as function definitions.
  - Tool calls are returned on message tool call fields and arguments are JSON strings that need defensive parsing.
  - Usage metadata is optional response metadata and should be read defensively.
  - SDK exceptions can expose request metadata; reports should store only redacted compact error text.
- Repo files:
  - `dashagent/llm_client.py`
  - `scripts/check_llm_sdk_backend.py`

## Anthropic Python SDK

- Context7 library ID: `/anthropics/anthropic-sdk-python`
- Result: `found`
- Query: `messages tool use usage fields`
- Risk: `medium`
- Code audit needed: `True`
- Findings:
  - Messages API calls use the SDK client's messages.create method.
  - Anthropic tools use name, description, and input_schema fields, and tool_use blocks return structured input.
  - Tool results are sent back as user content with a tool_result block.
  - Usage includes input/output token fields and should be normalized defensively.
- Repo files:
  - `dashagent/llm_client.py`

## Adobe Experience Platform API

- Context7 library ID: `/websites/developer_adobe_experience-platform-apis_references`
- Result: `found`
- Query: `headers x-api-key x-gw-ims-org-id sandbox authorization`
- Risk: `high`
- Code audit needed: `True`
- Findings:
  - AEP requests require Authorization, x-api-key, and x-gw-ims-org-id headers; sandbox-scoped endpoints also use x-sandbox-name.
  - Header names can be reported, but values must remain fully redacted or represented as constructible booleans only.
  - Endpoint-level permission, sandbox, and path errors are separate from global credential readiness.
  - Data endpoint diagnostics must stay GET-only unless explicitly limited to OAuth token acquisition.
- Repo files:
  - `dashagent/api_client.py`
  - `dashagent/adobe_env.py`
  - `dashagent/api_outcome_classifier.py`
  - `scripts/check_adobe_env_local.py`
  - `scripts/audit_live_adobe_api_readiness.py`
  - `scripts/run_live_api_readiness_smoke.py`
  - `scripts/run_post_permission_live_api_verification.py`

## DuckDB Python

- Context7 library ID: `/duckdb/duckdb-python`
- Result: `found`
- Query: `execute query parameters read only python result fetch`
- Risk: `medium`
- Code audit needed: `True`
- Findings:
  - DuckDB Python executes SQL through connection execute/sql APIs and fetches rows through fetch methods.
  - The client can execute multiple statements, so repository validation must block multi-statement and write statements before execution.
  - Parameter binding is available for values, but repository-generated SQL remains read-only validated text.
- Repo files:
  - `dashagent/db.py`
  - `dashagent/validators.py`

## SQLGlot

- Context7 library ID: `/websites/sqlglot`
- Result: `found`
- Query: `parse_one sql dialect validation read only expression`
- Risk: `medium`
- Code audit needed: `True`
- Findings:
  - parse_one parses a SQL string into a syntax tree for a chosen dialect.
  - Multiple statements can parse into a Block expression; repo validation should still block multi-statement SQL explicitly.
  - Parse errors should be warnings or validation failures, not uncontrolled crashes.
- Repo files:
  - `dashagent/sql_ast_tools.py`
  - `dashagent/validators.py`

## Pydantic v2

- Context7 library ID: `/pydantic/pydantic`
- Result: `found`
- Query: `model_dump BaseModel JSON serialization`
- Risk: `low`
- Code audit needed: `True`
- Findings:
  - Pydantic v2 SDK response models support model_dump for dictionary serialization.
  - JSON-safe output may require mode=json or model_dump_json when serializing datetime-like values.
  - Validation errors should be caught and reported safely where user-facing diagnostics are written.
- Repo files:
  - `dashagent/llm_client.py`

## Typer

- Context7 library ID: `/fastapi/typer`
- Result: `found`
- Query: `cli option argparse testing`
- Risk: `low`
- Code audit needed: `True`
- Findings:
  - Typer documents explicit CLI options and help output, but this repo primarily uses argparse for diagnostics.
  - CLI override flags should remain explicit user inputs rather than implicit environment behavior.
  - Required options and callbacks should fail clearly in help/error paths.
- Repo files:
  - `scripts/run_live_api_readiness_smoke.py`
  - `scripts/run_dev_eval.py`

## pytest

- Context7 library ID: `/pytest-dev/pytest`
- Result: `found`
- Query: `tmp_path monkeypatch capsys fixtures`
- Risk: `low`
- Code audit needed: `True`
- Findings:
  - pytest fixtures such as tmp_path, monkeypatch, and capsys are function-scoped tools for isolated tests.
  - monkeypatch changes are automatically undone after the test or fixture scope.
  - tmp_path provides per-test filesystem isolation for generated reports.
  - capsys supports output-redaction tests without printing secret values.
- Repo files:
  - `tests`
