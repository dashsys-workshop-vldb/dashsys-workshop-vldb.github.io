# Strict Eval After Smoke Timeout Grounding Audit

Source eval: `outputs/reports/local_qwen_v2_benchmark/partials_after_smoke_timeout_fix/eval_results_partial.json`

Classification basis: manual objective answer grounding from runtime evidence and trajectories; raw organizer-style scores are not used as correctness.

## Summary

- Rows reviewed: `35`
- Verdict counts: `{'PASS': 5, 'FAIL': 10, 'UNCLEAR': 20}`
- Gate-reported unsupported claims: `0`
- Gate-reported missing required fields: `0`
- Gate-reported scope errors after final repair: `0`
- Initial semantic gate failures before repair: `6`
- Final semantic gate failures: `0`

## Initial Gate Failures Before Repair

Final semantic gate failures after repair were `0`, but these rows had an initial gate failure before repair:

| Row | Final manual verdict | Note |
|---|---:|---|
| `example_003` | FAIL | All lookup rows for SMS Opt-In audience/destination were empty; final answer nevertheless asserts a connected audience and omits requested audience fields. |
| `example_006` | FAIL | Final answer dumps raw pass evidence and relationships rather than answering the requested dataset count using the same schema. |
| `example_009` | PASS | Schema details in the final answer are supported by the dim_blueprint row. |
| `example_010` | FAIL | Prompt asks XDM Experience Event schemas enabled for profile; SQL queried dim_collection NAME equality and profile fields, so the final count does not establish the requested schema count. |
| `example_021` | FAIL | SQL returned zero rows for the schema class lookup and API was unavailable; final answer includes an unsupported examples-include phrase and does not provide a default merge policy. |
| `example_034` | UNCLEAR | Final answer gives a local count and scoped live-API-unavailable caveat. It is grounded to executed evidence, but the metric/source semantics are not strong enough to mark PASS. |

## Row Classifications

| Row | Verdict | SQL/API | Objective issue | Evidence note |
|---|---:|---:|---|---|
| `example_000` | FAIL | 1/0 | unsupported_claim; missing_required_info | SQL returned the journey name but no publication date. Final answer adds published status and still does not answer when. (SQL rows 1) |
| `example_001` | PASS | 1/0 | none | Inactive/non-active journey names are directly supported by dim_campaign rows where STATUS != ACTIVE. (SQL rows 2) |
| `example_002` | PASS | 1/0 | none | Journey names, IDs, and statuses are directly supported by the local dim_campaign rows. (SQL rows 2) |
| `example_003` | FAIL | 4/0 | unsupported_claim; missing_required_info | All lookup rows for SMS Opt-In audience/destination were empty; final answer nevertheless asserts a connected audience and omits requested audience fields. (SQL rows 0,0,0,1) |
| `example_004` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | API-only evidence was dry-run unavailable; final answer is a safe caveat with no concrete unsupported data. (API dry-run:fail) |
| `example_005` | FAIL | 1/0 | missing_required_info; scope_caveat_error | Prompt asks all b2b-prod destinations sorted by modified with all columns. Evidence query filtered STATE=ACTIVE and returned zero; final no-match caveat is not enough for requested scope. (SQL rows 0) |
| `example_006` | FAIL | 2/0 | missing_required_info; answer_shape_error | Final answer dumps raw pass evidence and relationships rather than answering the requested dataset count using the same schema. (SQL rows 0,27) |
| `example_007` | UNCLEAR | 1/0 | possible_missing_required_info | SQL returned zero for a schema-label bridge lookup; final no-match caveat is safe, but coverage of the named schema is not proven complete. (SQL rows 0) |
| `example_008` | UNCLEAR | 1/0 | possible_missing_required_info | SQL returned zero for ALTDISPLAYTITLE lookup; final no-match caveat is safe, but field lookup completeness is not proven. (SQL rows 0) |
| `example_009` | PASS | 1/0 | none | Schema details in the final answer are supported by the dim_blueprint row. (SQL rows 1) |
| `example_010` | FAIL | 2/0 | missing_required_info | Prompt asks XDM Experience Event schemas enabled for profile; SQL queried dim_collection NAME equality and profile fields, so the final count does not establish the requested schema count. (SQL rows 1,0) |
| `example_011` | PASS | 1/0 | none | Count 74 is directly supported by COUNT(*) over dim_blueprint. (SQL rows 1) |
| `example_012` | UNCLEAR | 0/3 | missing_required_info_due_api_unavailable | All required API evidence was dry-run unavailable; final answer is a safe runtime-unavailable caveat. (API dry-run:fail,dry-run:fail,dry-run:fail) |
| `example_013` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Audit API evidence was dry-run unavailable; final answer is a safe runtime-unavailable caveat. (API dry-run:fail) |
| `example_014` | UNCLEAR | 1/0 | possible_scope_gap | Local schema entity query returned zero and final no-match caveat is safe, but all-entity scope may exceed dim_blueprint only. (SQL rows 0) |
| `example_015` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Tags API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_016` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Tags API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_017` | UNCLEAR | 0/2 | missing_required_info_due_api_unavailable | Tag category/tag API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail,dry-run:fail) |
| `example_018` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Tag details API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_019` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Merge policy API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_020` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Merge policy API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_021` | FAIL | 1/1 | unsupported_claim; missing_required_info; scope_caveat_error | SQL returned zero rows for the schema class lookup and API was unavailable; final answer includes an unsupported examples-include phrase and does not provide a default merge policy. (SQL rows 0; API dry-run:fail) |
| `example_022` | PASS | 1/0 | none | Count 13 is directly supported by COUNT(*) over dim_segment. (SQL rows 1) |
| `example_023` | FAIL | 0/1 | missing_required_info; over_caveat | Prompt asks list all segment definitions; V2 used only live API, but the same run proves local dim_segment evidence exists. Final global unavailable omits available local list evidence. (API dry-run:fail) |
| `example_024` | FAIL | 0/1 | missing_required_info; over_caveat | Prompt asks most recently updated segment definitions; V2 used only live API despite local dim_segment being available for segment definitions. Final unavailable omits local evidence path. (API dry-run:fail) |
| `example_025` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Segment jobs API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_026` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Segment jobs API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_027` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Segment jobs API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_028` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Catalog batches API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_029` | FAIL | 0/0 | missing_required_info; evidence_gap | Concrete batch-status count produced planner_success=false, compiled no SQL/API, executed no tools, and returned unavailable. (no tools) |
| `example_030` | FAIL | 0/0 | missing_required_info; evidence_gap | Concrete batch detail prompt produced planner_success=false, compiled no SQL/API, executed no tools, and returned unavailable. (no tools) |
| `example_031` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Export batch files API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_032` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Failed-files API evidence was dry-run unavailable; final answer is safe. (API dry-run:fail) |
| `example_033` | UNCLEAR | 0/1 | missing_required_info_due_api_unavailable | Time-series metric evidence was dry-run unavailable through the selected API path; final answer is safe. (API dry-run:fail) |
| `example_034` | UNCLEAR | 1/1 | partial_answer_with_api_unavailable | Final answer gives a local count and scoped live-API-unavailable caveat. It is grounded to executed evidence, but the metric/source semantics are not strong enough to mark PASS. (SQL rows 1; API dry-run:fail) |

## Notable Examples

- `example_000` `FAIL`: SQL returned the journey name but no publication date. Final answer adds published status and still does not answer when. Final: The journey named 'Birthday Message' is published, but the local snapshot does not contain a value for the STARTDATE or LASTDEPLOYEDTIME fields, so the specific publication date is not available.
- `example_003` `FAIL`: All lookup rows for SMS Opt-In audience/destination were empty; final answer nevertheless asserts a connected audience and omits requested audience fields. Final: The segment audience named SMS Opt-In is connected to the SMS Opt-In destination and is used in 0 other audiences. Details such as audienceId, totalProfiles, createdTime, and updatedTime were not available in the local runtime evidence.
- `example_006` `FAIL`: Final answer dumps raw pass evidence and relationships rather than answering the requested dataset count using the same schema. Final: Local snapshot evidence shows t2/SQL/LOCAL_SNAPSHOT: count: 0 | t3/SQL/LOCAL_SNAPSHOT: count: 27; relationship: COLLECTIONID:69c8db5194a54c8d91aa2ddc -> BLUEPRINTID:7e1625ee727af05a1eca4e214a3ad0d063a42c78ff4aab4a; relationship: LABELSBLUEPRINT:[] -> COLLECTIONID:69c8db5194a54c8d91aa2ddc; relationship: LABELSBLUEPRINT:[] -> BLUEPRINTID:7e1625ee727af05a1eca4e214a3ad0d063a42c78ff4aab4a; id: 69c8db5194a54c8d91aa2ddc; id: 7e1625ee727af05a1eca4e214a3ad0d063a42c78ff4aab4a. Some requested runtime evidence was unavailable for this query/scope.
- `example_021` `FAIL`: SQL returned zero rows for the schema class lookup and API was unavailable; final answer includes an unsupported examples-include phrase and does not provide a default merge policy. Final: Local snapshot evidence shows task_schema_lookup/SQL/LOCAL_SNAPSHOT: count: 0; examples include _xdm.context.profile. Live API evidence was unavailable, so a live comparison cannot be completed.
- `example_023` `FAIL`: Prompt asks list all segment definitions; V2 used only live API, but the same run proves local dim_segment evidence exists. Final global unavailable omits available local list evidence. Final: Runtime evidence was unavailable; cannot provide a verified answer.
- `example_029` `FAIL`: Concrete batch-status count produced planner_success=false, compiled no SQL/API, executed no tools, and returned unavailable. Final: Runtime evidence was unavailable; cannot provide a verified answer.
- `example_034` `UNCLEAR`: Final answer gives a local count and scoped live-API-unavailable caveat. It is grounded to executed evidence, but the metric/source semantics are not strong enough to mark PASS. Final: Local snapshot evidence shows task_ingestion_counts/SQL/LOCAL_SNAPSHOT: count: 0; count:0. Live API evidence was unavailable, so a live comparison cannot be completed.
