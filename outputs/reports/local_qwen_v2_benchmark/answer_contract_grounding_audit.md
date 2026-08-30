# V2 Answer Contract Grounding Audit

## Scope
- Uses latest available partial local Qwen V2 smoke rows.
- Strict dev eval was not run because smoke did not pass.

## Totals
- rows_seen: 4
- PASS: 2
- FAIL: 2
- unsupported_claims: 0
- no_tool_fp: 2
- final_semantic_gate_final_failures: 0

## Row Classifications
| prompt_id | class | route | SQL | API | facts | no_tool_fp | note |
|---|---:|---|---:|---:|---:|---:|---|
| pure_concept_schema | PASS | LLM_DIRECT | 0 | 0 | 0 | False | Expected route/evidence behavior satisfied with unsupported_claims=0. |
| pure_meta_list_schemas | PASS | LLM_DIRECT | 0 | 0 | 0 | False | Expected route/evidence behavior satisfied with unsupported_claims=0. |
| ambiguous_user_schemas | FAIL | EVIDENCE_PIPELINE | 0 | 0 | 0 | True | Smoke expectation failed. |
| local_schema_count | FAIL | EVIDENCE_PIPELINE | 0 | 0 | 0 | True | Smoke expectation failed. |

## Contract/Planner Errors
- missing_answer_contract_rows: [{'prompt_id': 'ambiguous_user_schemas', 'error_type': 'missing_answer_contract', 'error_message': 'EVIDENCE route requires answer_contract.required_slots.', 'answer_contract_error_type': 'missing_answer_contract'}]
- unknown_table_rows: [{'prompt_id': 'local_schema_count', 'error_type': 'unknown_table', 'error_message': 'Unknown table: catalog_datasets', 'answer_contract_error_type': None}]
