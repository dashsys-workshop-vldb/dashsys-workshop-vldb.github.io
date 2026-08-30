# SDK Tool Calling Promotion Plan

- Selected candidate: `combined_safe_tool_policy`
- Packaged strategy changed: `False`
- Final submission format changed: `False`

## Parts
- `compact_tool_schema`: `implemented` - two-tool SDK baseline schema descriptions only
- `compact_tool_result_evidence_summary`: `implemented` - native tool-result message payloads passed back to SDK LLM paths
- `allowed_tools_by_prompt_type`: `implemented` - route-based tool exposure for LLM baseline paths; API_REQUIRED/API_ONLY remains API-capable
- `no_rewrite_when_backend_complete`: `implemented` - controller/shadow path skips rewrite when backend answer already contains required supported signal
- `parallel_tool_calls_control`: `implemented_openai_only` - OpenAI-compatible SDK payload can set parallel_tool_calls=false; Anthropic path ignores safely

## Required Validation
- python3 scripts/run_correctness_efficiency_scorecard.py
- python3 scripts/run_dev_eval.py --strict
- python3 scripts/run_hidden_style_eval.py
- python3 scripts/run_generated_prompt_suite_local_diagnostic.py
- python3 scripts/check_submission_ready.py
- python3 scripts/generate_sdk_usage_audit.py
- python3 -m pytest -q
