# Smoke Timeout Regression Triage

- Packaged default changed: `False`
- Timed-out prompt: `compare_local_live_birthday_status`
- Last stage: `checkpoint_llm_unified_planner_start`
- LLM response returned: `False`
- Pre-fix total message+tool chars: `32238`
- Pre-fix schema card chars: `11499`
- Pre-fix API card chars: `7441`
- Root cause primary: `C. semantic_ir_context_card_too_large`
- Root cause secondary: `A. planner_prompt_too_large`

The timeout occurred before a planner response was returned, with zero SQL/API calls. The evidence points to planner/context size sensitivity in the local Qwen toolcall path, not SQL/API execution or final grounding.
