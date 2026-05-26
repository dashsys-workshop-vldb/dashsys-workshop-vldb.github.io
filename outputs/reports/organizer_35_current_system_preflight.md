# Organizer 35 Current System Preflight

- Testset path: `/Users/tanqinyang/Desktop/dashsys-workshop-vldb/data/data.json`
- Examples: `35`
- Evaluator: `scripts/run_dev_eval.py --strict`
- Packaged default strategy: `SQL_FIRST_API_VERIFY`
- Combined-safe hooks present: `True`
- Applied trial can be evaluated without default change: `True`
- Live API enabled for strict eval: `False`

## Current SQL_FIRST_API_VERIFY Strict Snapshot

```json
{
  "avg_answer_score": 0.3207,
  "avg_answer_time": 0.0115,
  "avg_api_score": 0.9791,
  "avg_correctness_score": 0.685,
  "avg_estimated_tokens": 799.2286,
  "avg_execution_time": 0.5376,
  "avg_final_score": 0.6582,
  "avg_metadata_tokens": 817.5429,
  "avg_planning_time": 0.0008,
  "avg_preprocessing_time": 0.0033,
  "avg_prompt_tokens": 1459.6286,
  "avg_runtime": 0.5676,
  "avg_sql_score": 0.9333,
  "avg_tool_call_count": 1.4571
}
```

## Module Presence

- `staged_evidence_policy`: `True`
- `post_sql_deterministic_policy`: `True`
- `post_sql_decision_card`: `True`
- `post_sql_api_call_verifier`: `True`
- `semantic_route_decision_ladder`: `True`

Credential values were not read or printed. Hidden-style and check_submission_ready are rerun in validation.
