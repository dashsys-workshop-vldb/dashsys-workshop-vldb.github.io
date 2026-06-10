# Unsafe Answer Candidate Analysis

- Rows: 103
- Positive supportable rows: 18
- Top supportable rows: ['example_031', 'example_031', 'example_031', 'example_031', 'example_031', 'example_030', 'example_030', 'example_030', 'example_030', 'example_030']
- Packaged execution changed: False

## Category Counts

- `answer_drift`: 77
- `dry_run_label_loss`: 2
- `no_accuracy_relevant_candidate_change`: 9
- `no_score_or_correctness_improvement`: 78
- `token_gate_failed`: 28

## Top Rows

- `example_031` `compact_endpoint_unavailable` supportable_delta=0.2171 categories=['token_gate_failed'] reason=global_token_gate_failed
- `example_031` `minimal_endpoint_fact` supportable_delta=0.2171 categories=['token_gate_failed'] reason=claim_validation_failed; answer_token_budget_failed; global_token_gate_failed
- `example_031` `query_entity_plus_endpoint` supportable_delta=0.2149 categories=['token_gate_failed'] reason=claim_validation_failed; answer_token_budget_failed; global_token_gate_failed
- `example_031` `endpoint_params_plus_unavailable` supportable_delta=0.2145 categories=['token_gate_failed'] reason=claim_validation_failed; answer_token_budget_failed; global_token_gate_failed
- `example_031` `answer_only` supportable_delta=0.1994 categories=['token_gate_failed'] reason=token_gate_failed
- `example_030` `compact_endpoint_unavailable` supportable_delta=0.1471 categories=['token_gate_failed'] reason=global_token_gate_failed
- `example_030` `query_entity_plus_endpoint` supportable_delta=0.1427 categories=['token_gate_failed'] reason=claim_validation_failed; answer_token_budget_failed; global_token_gate_failed
- `example_030` `answer_only` supportable_delta=0.1413 categories=['token_gate_failed'] reason=token_gate_failed
- `example_030` `minimal_endpoint_fact` supportable_delta=0.1395 categories=['token_gate_failed'] reason=claim_validation_failed; answer_token_budget_failed; global_token_gate_failed
- `example_030` `endpoint_params_plus_unavailable` supportable_delta=0.139 categories=['token_gate_failed'] reason=claim_validation_failed; answer_token_budget_failed; global_token_gate_failed
- `example_021` `answer_shape_list` supportable_delta=0.0016 categories=['no_accuracy_relevant_candidate_change'] reason=no_accuracy_relevant_candidate_change
- `example_025` `answer_shape_list` supportable_delta=0.001 categories=['no_accuracy_relevant_candidate_change'] reason=no_accuracy_relevant_candidate_change
- `example_024` `answer_shape_date` supportable_delta=0.0009 categories=['no_accuracy_relevant_candidate_change'] reason=no_accuracy_relevant_candidate_change
- `example_029` `answer_shape_count` supportable_delta=0.0008 categories=['no_accuracy_relevant_candidate_change'] reason=no_accuracy_relevant_candidate_change
- `example_028` `answer_shape_date` supportable_delta=0.0008 categories=['no_accuracy_relevant_candidate_change'] reason=no_accuracy_relevant_candidate_change
