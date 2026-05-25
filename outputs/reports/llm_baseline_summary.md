# LLM Baseline Summary

- Framework: `generic_sdk_llm_baseline`
- Current backend/model: `qwen2.5-32b-instruct`
- Provider/backend type: `openai_compatible` / `openai_sdk`
- Anthropic SDK support: available_in_client; configure LLM_PROVIDER=anthropic with ANTHROPIC_API_KEY
- Tool calling supported: `True`
- Best LLM baseline: `LLM_CONTROLLER_OPTIMIZED_AGENT`
- Best LLM baseline score: `0.6328`
- Pure LLM tool-agent pass: best `LLM_CONTROLLER_OPTIMIZED_AGENT`; score `0.6328`; new rows `1`; gate `blocked_by_unsupported_claims`
- SQL_FIRST_API_VERIFY score: `0.6553`
- Recommendation: `keep_shadow_only`
- LLM semantic routing helper: `do_not_promote` (complete)
- Semantic router isolated trial: `complete`; promotion decision: `do_not_promote`
- Decision-stage feedback-loop status: `candidate_not_viable_after_feedback_loops`
- Evidence-aware answer synthesis: `keep_trial_only`
- SDK tool-calling optimization: `speed_only_shadow_candidates_no_promotion`; best variant `combined_safe_tool_policy`; runtime change applied `False`
- Correctness + efficiency evaluation: `speed_only_patch_needs_validation`; best candidate `compact_tool_schema`; official overall score claim `False`
- Reason: Deterministic SQL_FIRST_API_VERIFY remains higher under strict scoring.

The LLM baseline framework is generic; Qwen is only the current configured backend/model metadata.
