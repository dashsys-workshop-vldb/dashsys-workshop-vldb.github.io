# Gemini OpenAI SDK Payload Debug

Compares the known-working raw REST payload shape against the OpenAI SDK payload shape.

- base_url: `https://generativelanguage.googleapis.com/v1beta/openai/`
- model: `gemini-3.5-flash`
- api_key_present: `True`
- raw_rest_ok: `False`
- raw_rest_tool_calls_count: `0`
- raw_rest_finish_reason: `None`
- sdk_ok: `False`
- sdk_tool_calls_count: `0`
- sdk_finish_reason: `None`
- raw_rest_payload_keys: `['model', 'messages', 'tools', 'tool_choice']`
- sdk_payload_keys: `['model', 'messages', 'tools', 'tool_choice']`
- sdk_missing_keys: `[]`
- sdk_extra_keys: `[]`
- same_order: `True`
- sdk_gemini_openai_compat_mode: `True`
- sdk_omitted_for_gemini: `['temperature', 'max_tokens', 'parallel_tool_calls']`

Raw REST error: `HTTP 400: <html><title>Error 400 (Bad Request)!!1</title></html>`

SDK error: `<html><title>Error 400 (Bad Request)!!1</title></html>`
