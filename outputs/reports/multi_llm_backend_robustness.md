# Multi-LLM Backend Robustness

Diagnostic-only backend sensitivity report. No hosted LLM calls are executed by this script.

- LLM calls executed: `0`
- No-LLM template dependency score: `0.1998`

## Backends

- `deterministic_only`: status `baseline_deterministic_path`, available `True`, executed `True`
- `no_llm_fallback`: status `fallback_path_no_model_required`, available `True`, executed `True`
- `openai`: status `available_not_executed_diagnostic_only`, available `True`, executed `False`
- `openrouter`: status `available_not_executed_diagnostic_only`, available `True`, executed `False`
- `anthropic`: status `unavailable`, available `False`, executed `False`

Variance across hosted model backends is recorded as unavailable in this pass because executing hosted LLM calls is outside the current local-first diagnostic scope.
