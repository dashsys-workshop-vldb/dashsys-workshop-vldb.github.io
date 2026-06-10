# Gemini OpenAI-Compatible Compatibility Debug

Minimal chat-completions matrix only. This report does not run V2 smoke, Pioneer, or benchmarks.

- Classification: `endpoint_or_base_url_contract_problem`
- GEMINI_API_KEY present: `True`
- Env source: `.env.local`
- OpenAI SDK available: `True`
- Basic no-tools any ok: `False`
- Tool payload any ok: `False`
- Tool call any returned: `False`
- Bad-request 400 cells: `32` / `32`
- V2 smoke should run now: `False`

## Matrix

| Base URL | Model | Payload | OK | Category | 400? | Finish | Content? | Tool Calls | Error |
|---|---|---|---:|---|---:|---|---:|---:|---|
| `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-flash-latest` | `basic_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-flash-latest` | `simple_json_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-flash-latest` | `tool_auto` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-flash-latest` | `tool_forced` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `models/gemini-flash-latest` | `basic_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `models/gemini-flash-latest` | `simple_json_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `models/gemini-flash-latest` | `tool_auto` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `models/gemini-flash-latest` | `tool_forced` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` | `basic_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` | `simple_json_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` | `tool_auto` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` | `tool_forced` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `models/gemini-2.0-flash` | `basic_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `models/gemini-2.0-flash` | `simple_json_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `models/gemini-2.0-flash` | `tool_auto` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai` | `models/gemini-2.0-flash` | `tool_forced` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-flash-latest` | `basic_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-flash-latest` | `simple_json_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-flash-latest` | `tool_auto` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-flash-latest` | `tool_forced` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `models/gemini-flash-latest` | `basic_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `models/gemini-flash-latest` | `simple_json_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `models/gemini-flash-latest` | `tool_auto` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `models/gemini-flash-latest` | `tool_forced` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` | `basic_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` | `simple_json_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` | `tool_auto` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` | `tool_forced` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `models/gemini-2.0-flash` | `basic_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `models/gemini-2.0-flash` | `simple_json_no_tools` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `models/gemini-2.0-flash` | `tool_auto` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |
| `https://generativelanguage.googleapis.com/v1beta/openai/` | `models/gemini-2.0-flash` | `tool_forced` | `False` | `bad_request_400` | `True` | `` | `False` | `0` | <html><title>Error 400 (Bad Request)!!1</title></html> |

## Interpretation Rules

- If basic no-tools fails for all cells, classification is `endpoint_or_base_url_contract_problem`.
- If basic no-tools succeeds but all tool payloads fail, classification is `tools_schema_or_tool_choice_problem`.
- If `tool_auto` succeeds but all forced tool-choice cells fail, classification is `forced_tool_choice_not_supported`.
- If any tool payload succeeds, classification is `toolcall_supported` unless the forced-only distinction above applies.
