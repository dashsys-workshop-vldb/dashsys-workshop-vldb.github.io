# Overnight Iteration 1 Result

- Status: `promoted`
- Strict score: `0.6491` → `0.6553` (`0.0062`)
- Correctness: `0.6743` → `0.6805` (`0.0062`)
- Answer score: `0.3076` → `0.3199` (`0.0123`)
- Tool calls: `1.4571` → `1.4571`
- Hidden-style: `48/48`
- Readiness: `True`
- Secret scan: `passed_no_hits`
- SQL/API/tool drift count: `0`
- Answer changed rows: `example_028, example_029, example_030, example_031`

## Promoted Changes

- Batch-family dry-run endpoint-aware unavailable answer wording, backed by recorded API endpoint path/params only.

## Shadow-Only / Rejected

- Broad endpoint-aware dry-run wording for non-batch families was trialed in /tmp and rejected because strict score regressed to 0.6447.
- LLM baseline remains keep_shadow_only.

## Diff Stat

```
 dashagent/answer_reranker.py                       |     9 +-
 dashagent/answer_slots.py                          |    19 +
 dashagent/answer_templates.py                      |    81 +
 .../trajectory.json                                |    70 +-
 .../llm_free_agent_baseline/trajectory.json        |    70 +-
 .../sql_first_api_verify/trajectory.json           |    70 +-
 .../example_000/sql_only_baseline/trajectory.json  |    70 +-
 .../example_000/template_first/trajectory.json     |    70 +-
 .../trajectory.json                                |    66 +-
 .../llm_free_agent_baseline/trajectory.json        |    66 +-
 .../sql_first_api_verify/trajectory.json           |    66 +-
 .../example_001/sql_only_baseline/trajectory.json  |    66 +-
 .../example_001/template_first/trajectory.json     |    66 +-
 .../trajectory.json                                |    64 +-
 .../llm_free_agent_baseline/trajectory.json        |    64 +-
 .../sql_first_api_verify/trajectory.json           |    64 +-
 .../example_002/sql_only_baseline/trajectory.json  |    64 +-
 .../example_002/template_first/trajectory.json     |    64 +-
 .../trajectory.json                                |    70 +-
 .../llm_free_agent_baseline/trajectory.json        |    70 +-
 .../sql_first_api_verify/trajectory.json           |    70 +-
 .../example_003/sql_only_baseline/trajectory.json  |    70 +-
 .../example_003/template_first/trajectory.json     |    70 +-
 .../trajectory.json                                |    66 +-
 .../llm_free_agent_baseline/trajectory.json        |    66 +-
 .../sql_first_api_verify/trajectory.json           |    66 +-
 .../example_004/sql_only_baseline/trajectory.json  |    66 +-
 .../example_004/template_first/trajectory.json     |    66 +-
 .../trajectory.json                                |    70 +-
 .../llm_free_agent_baseline/trajectory.json        |    70 +-
 .../sql_first_api_verify/trajectory.json           |    70 +-
 .../example_005/sql_only_baseline/trajectory.json  |    70 +-
 .../example_005/template_first/trajectory.json     |    70 +-
 .../trajectory.json                                |    64 +-
 .../llm_free_agent_baseline/trajectory.json        |    64 +-
 .../sql_first_api_verify/trajectory.json           |    64 +-
 .../example_006/sql_only_baseline/trajectory.json  |    64 +-
 .../example_006/template_first/trajectory.json     |    64 +-
 .../trajectory.json                                |    70 +-
 .../llm_free_agent_baseline/trajectory.json        |    70 +-
 .../sql_first_api_verify/trajectory.json           |    70 +-
 .../example_007/sql_only_baseline/trajectory.json  |    70 +-
 .../example_007/template_first/trajectory.json     |    70 +-
 .../trajectory.json                                |    64 +-
 .../llm_free_agent_baseline/trajectory.json        |    64 +-
 .../sql_first_api_verify/trajectory.json           |    64 +-
 .../example_008/sql_only_baseline/trajectory.json  |    64 +-
 .../example_008/template_first/trajectory.json     |    64 +-
 .../trajectory.json                                |    68 +-
 .../llm_free_agent_baseline/trajectory.json        |    68 +-
 .../sql_first_api_verify/trajectory.json           |    68 +-
 .../example_009/sql_only_baseline/trajectory.json  |    68 +-
 .../example_009/template_first/trajectory.json     |    68 +-
 .../trajectory.json                                |    68 +-
 .../llm_free_agent_baseline/trajectory.json        |    68 +-
 .../sql_first_api_verify/trajectory.json           |    68 +-
 .../example_010/sql_only_baseline/trajectory.json  |    68 +-
 .../example_010/template_first/trajectory.json     |    68 +-
 .../trajectory.json                                |    64 +-
 .../llm_free_agent_baseline/trajectory.json        |    64 +-
 .../sql_first_api_verify/trajectory.json           |    64 +-
 .../example_011/sql_only_baseline/trajectory.json  |    64 +-
 .../example_011/template_first/trajectory.json     |    64 +-
 .../trajectory.json                                |    68 +-
 .../llm_free_agent_baseline/trajectory.json        |    68 +-
 .../sql_first_api_verify/trajectory.json           |    68 +-
 .../example_012/sql_only_baseline/trajectory.json  |    68 +-
 .../example_012/template_first/trajectory.json     |    68 +-
 .../trajectory.json                                |    64 +-
 .../llm_free_agent_baseline/trajectory.json        |    64 +-
 .../sql_first_api_verify/trajectory.json           |    64 +-
 .../example_013/sql_only_baseline/trajectory.json  |    64 +-
 .../example_013/template_first/trajectory.json     |    64 +-
 .../trajectory.json                                |    64 +-
 .../llm_free_agent_baseline/trajectory.json        |    64 +-
 .../sql_first_api_verify/trajectory.json           |    64 +-
 .../example_014/sql_only_baseline/trajectory.json  |    64 +-
 .../example_014/template_first/trajectory.json     |    64 +-
 .../trajectory.json                                |    62 +-
 .../llm_free_agent_baseline/trajectory.json        |    64 +-
 .../sql_first_api_verify/trajectory.json           |    62 +-
 .../example_015/sql_only_baseline/trajectory.json  |    64 +-
 .../example_015/template_first/trajectory.json     |    64 +-
 .../trajectory.json                                |    62 +-
 .../llm_free_agent_baseline/trajectory.json        |    64 +-
 .../sql_first_api_verify/trajectory.json           |    62 +-
 .../example_016/sql_only_baseline/trajectory.json  |    64 +-
 .../example_016/template_first/trajectory.json     |    62 +-
 .../trajectory.json                                |    64 +-
 .../llm_free_agent_baseline/trajectory.json        |    66 +-
 .../sql_first_api_verify/trajectory.json           |    64 +-
 .../example_017/sql_only_baseline/trajectory.json  |    66 +-
 .../example_017/template_first/trajectory.json     |    64 +-
 .../trajectory.json                                |    64 +-
 .../llm_free_agent_baseline/trajectory.json        |    66 +-
 .../sql_first_ap
```
