# Smoke Timeout Regression Fix Summary

## Implementation
- Added mechanical Semantic IR planner card compaction with a default 24k character budget.
- Compacted always-on planner rules and JSON payloads while preserving LLM ownership of route/source/table/field/endpoint decisions.
- Added pre-call prompt diagnostics to the executor heartbeat.
- Added tests for prompt budget, compact relation guidance, and preserved formal card shape.

## Prompt Size
- Before total message+tool chars: `32238`
- After total message+tool chars: `23441`
- After schema card chars: `7826` / original `10765`
- After API card chars: `5261` / original `7532`

## Fresh Smoke
- passed_count: `7` / `7`
- timeout_count: `0`
- unsupported_claims: `0`
- no_tool_fp: `0`
- final_semantic_gate_final_failures: `0`
- compare prompt timed_out: `False`; sql_calls `2`; api_calls `2`

## Strict V2 Eval
- row_count: `35` / `35`
- timeout_count: `0`
- failed_query_ids: `[]`
- avg_final_score: `0.2309`
- avg_correctness_score: `0.2827`
- avg_answer_score: `0.1967`

## Validation
- Focused tests: `59 passed`
- Full pytest: `1190 passed, 1 skipped`
- check_submission_ready: `ok=true`
- SDK usage audit runtime_llm_direct_http_hits: `0`
- git diff --check: `passed`

## Recommendation
- Safe to keep: `true`
- Safe to commit: `true`
- Safe to promote V2: `false`
