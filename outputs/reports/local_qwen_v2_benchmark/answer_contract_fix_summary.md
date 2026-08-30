# V2 Answer Contract Fix Summary

## Summary
- Answer Contract / Evidence Contract layer implemented for V2.
- Semantic IR primary path remains SDK toolcall-first; packaged default unchanged.
- Local Qwen tool-call probe passed.
- Fresh smoke did not complete/pass, so strict dev eval was not run.

## Smoke Summary
- partial_report: True
- row_count: 4
- passed_count: 2
- failed_count: 2
- unsupported_claims: 0
- no_tool_fp: 2

## Blockers
- Qwen still omitted answer_contract for ambiguous_user_schemas after one repair; contract gate failed closed with missing_answer_contract.
- local_schema_count failed before contract evaluation on planner-selected unknown table catalog_datasets; this is a Semantic IR table-selection/provider quality issue, not an answer-contract bug.
- Full smoke runner did not complete; dev eval remained gated off as required.

## Validation
- Full pytest: 1206 passed, 1 skipped
- check_submission_ready ok: True
- SDK direct HTTP hits: None
- git diff --check: passed
