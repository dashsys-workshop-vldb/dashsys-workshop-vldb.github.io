# Weak Model Harness Assertion Catalog

| Assertion | Severity | Repair hint |
| --- | --- | --- |
| `data_question_requires_tool` | `fatal` | Use execute_sql or call_api before answering data questions. |
| `sql_required_has_candidate` | `recoverable` | Produce a SQL candidate or explicit no-SQL reason. |
| `api_required_has_candidate` | `recoverable` | Choose a valid endpoint catalog candidate. |
| `sql_preconditions_before_execution` | `fatal` | Retrieve schema context, pass unit tests, pass SQLValidator, and parse SQL before execution. |
| `api_endpoint_catalog_valid` | `fatal` | Use a known GET endpoint without unresolved path parameters. |
| `api_no_unresolved_path_params` | `fatal` | Resolve path parameters through safe discovery or choose another endpoint. |
| `final_claims_supported` | `fatal` | Remove unsupported claims or render only EvidenceBus facts. |
| `sql_evidence_used_when_answering` | `recoverable` | Use direct SQL evidence in the final answer. |
| `api_evidence_used_when_required` | `recoverable` | Use required API evidence in the final answer. |
| `live_empty_not_global_no_data` | `fatal` | Treat live_empty as endpoint/context empty, not global no-data. |
| `api_error_not_no_data` | `fatal` | Treat api_error as unavailable evidence, not no data. |
