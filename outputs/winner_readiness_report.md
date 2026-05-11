# Winner Readiness Report

- Freshness run ID: `20260506T205804480909Z-885373750216791`
- Preferred strategy: `SQL_FIRST_API_VERIFY`
- Strict final score: 0.6552
- Estimated tokens/runtime/tools: 834.6 / 0.0157 / 1.4571
- Final submission ready: True
- Official-token packaged trial recommendation: `safe_to_make_packaged_default_in_future`
- Official-token promotion recommendation: `promoted_keep_enabled`
- Hidden-style passed/total: 48/48
- Hidden-style family/schema stability: 1.0 / 1.0
- Accuracy decision hidden-style fresh: True
- Endpoint-family risky rows: 35
- Endpoint/schema rule candidates: 10
- Endpoint/schema canary recommendation: `keep_shadow_only`
- Endpoint/schema packaged trial recommendation: `keep_shadow_only`
- AST-guided SQL canary recommendation: `keep_shadow_only`
- Repair selector v3 success: False
- Accuracy decision: `keep_all_accuracy_changes_shadow_only`
- 0.70 push achieved score: 0.6491
- 0.70 reached safely: False
- 0.70 push recommendation: `submit_current_official_token_reduction_version`
- Score-component API-correct answer-weak rows: 16
- Evidence-answer safe rows/projected score: 1 / 0.6494
- Answer-shape v2 changed/safe/projected score: 35 / 7 / 0.6497
- Unsafe answer analysis rows/positive supportable: 103 / 18
- Supportable answer rewrite safe rows/projected score: 4 / 0.6552
- LLM answer rewrite search: completed (recommendation: `keep_shadow_only`, model: openrouter/free, accepted: 0/6)
- LLM baseline framework: backend=qwen2.5-32b-instruct; backend_type=openai_sdk; strict=available; recommendation=`keep_shadow_only`
- Local fact coverage available/used/covered: 34 / 24 / 34
- Endpoint-family tie-break v2 shadow recommendation: `keep_shadow_only` (trial eligible rows: 0)
- Live-mode readiness diagnostic-only: True (dry-run dependent rows: 34)
- Autonomous packaged trial recommendation: `continue_iteration_target_not_reached`
- Autonomous 0.75 best score/reached: 0.6558 / False
- score075 integration merged/rejected/pending branches: 0 / 0 / 10
- Redundant file audit ran: True
- Cleanup applied/deleted/protected-ok: False / 0 / True
- Repair selector v2 success: False
- Final recommendation: `ready_to_submit_with_official_token_reduction`

## Recommended Next Action

- Submit with official-token reduction if the promotion report remains kept.
- Keep repair execution disabled.
- Keep compact context disabled.
- Use endpoint/schema rule candidates only as future canary inputs.
- Keep accuracy changes shadow-only unless the accuracy decision report explicitly recommends promotion.
- Use the 0.70 push report to decide whether any targeted accuracy change is worth a later explicit promotion.
- Use the autonomous 0.75 score-push report only after integration has merged and validated worker branches.
