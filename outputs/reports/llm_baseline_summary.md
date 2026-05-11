# LLM Baseline Summary

- Framework: `generic_sdk_llm_baseline`
- Current backend/model: `qwen2.5-32b-instruct`
- Provider/backend type: `openai_compatible` / `openai_sdk`
- Anthropic SDK support: available_in_client; configure LLM_PROVIDER=anthropic with ANTHROPIC_API_KEY
- Tool calling supported: `True`
- Best LLM baseline: `LLM_CONTROLLER_OPTIMIZED_AGENT`
- Best LLM baseline score: `0.6328`
- SQL_FIRST_API_VERIFY score: `0.6553`
- Recommendation: `keep_shadow_only`
- LLM semantic routing helper: `do_not_promote` (complete)
- Semantic router isolated trial: `complete`; promotion decision: `do_not_promote`
- Decision-stage feedback-loop status: `candidate_not_viable_after_feedback_loops`
- Reason: Deterministic SQL_FIRST_API_VERIFY remains higher under strict scoring.

The LLM baseline framework is generic; Qwen is only the current configured backend/model metadata.
