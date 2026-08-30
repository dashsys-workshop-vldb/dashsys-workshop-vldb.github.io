# SDK Tool-Call Surface Audit

- Diagnostic only: `True`
- Direct HTTP hits: `0`
- Recommendation: `trial_only_shadow_optimization`

| Issue | Area | Classification | Finding |
| --- | --- | --- | --- |
| `openai_sdk_client` | `openai_compatible` | `aligned` | OpenAI-compatible calls are routed through the OpenAI SDK client. |
| `openai_tool_choice` | `openai_compatible` | `aligned` | Tool choice is accepted by the shared generate_messages path. |
| `openai_parallel_tool_calls` | `openai_compatible` | `aligned` | OpenAI-compatible SDK payloads can explicitly disable parallel tool calls in deterministic SDK-tool paths. |
| `openai_usage_metadata` | `openai_compatible` | `aligned` | Usage metadata is read defensively when the SDK response contains it. |
| `anthropic_sdk_client` | `anthropic` | `aligned` | Anthropic calls are routed through the Anthropic SDK client. |
| `anthropic_tool_shape` | `anthropic` | `aligned` | OpenAI function tools are converted into Anthropic name/description/input_schema tools. |
| `anthropic_tool_use_normalization` | `anthropic` | `aligned` | Anthropic tool_use blocks are normalized into the shared tool-call shape. |
| `baseline_tool_schema_size` | `all_providers` | `aligned` | Baseline tool schema estimate is 693 characters. |
| `two_tools_always_available_baseline` | `all_providers` | `aligned` | The two-tool LLM baseline prunes exposed tools by deterministic prompt route before SDK calls. |
| `tool_result_message_size` | `all_providers` | `aligned` | Native tool-result messages use compact EvidenceBus-style summaries instead of raw previews. |
| `direct_http_guard` | `all_providers` | `aligned` | SDK usage audit reports runtime direct LLM HTTP hits. |
