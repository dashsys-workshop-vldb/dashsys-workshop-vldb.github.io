# Weak Model Generated Prompt Diagnostic

Diagnostic-only weak-scaffold run. Generated prompts are not official score evidence.

- Variant: `weak_scaffold_api_recovery_v1`
- Executed prompts: `50`
- Runtime pass: `50` / `50`
- Validation failures: `0`
- Unsupported claims: `0`
- SQL selected: `37`
- API selected: `45`
- Stable subset: `True`

## Top Failure Categories

- `no_clear_failure`: `24`
- `sql_compiler_gap`: `13`
- `wrong_columns`: `9`
- `wrong_table`: `4`

## Full 250 Escalation Attempt

- Attempted: `True`
- Completed: `False`
- Reason: `terminated_after_long_network_wait_without_final_artifact`
- Substitute validation: `completed_50_prompt_subset`
- Residual risk: `full_250_weak_scaffold_generated_prompt_behavior_not_confirmed_in_this_run`
