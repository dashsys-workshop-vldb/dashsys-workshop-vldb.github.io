# Unsafe Answer Candidate Analysis

- Rows: 24
- Positive supportable rows: 10
- Top supportable rows: ['example_031', 'example_030', 'example_021', 'example_025', 'example_024', 'example_029', 'example_028', 'example_031', 'example_030', 'example_019']
- Packaged execution changed: False

## Category Counts

- `answer_drift`: 8
- `dry_run_label_loss`: 2
- `runtime_or_tool_gate`: 24
- `token_gate_failed`: 9

## Top Rows

- `example_031` `answer_only` supportable_delta=0.1994 categories=['runtime_or_tool_gate', 'token_gate_failed'] reason=token_gate_failed
- `example_030` `answer_only` supportable_delta=0.1413 categories=['runtime_or_tool_gate', 'token_gate_failed'] reason=token_gate_failed
- `example_021` `answer_shape_list` supportable_delta=0.0016 categories=['runtime_or_tool_gate'] reason=no_accuracy_relevant_candidate_change
- `example_025` `answer_shape_list` supportable_delta=0.001 categories=['runtime_or_tool_gate'] reason=no_accuracy_relevant_candidate_change
- `example_024` `answer_shape_date` supportable_delta=0.0009 categories=['runtime_or_tool_gate'] reason=no_accuracy_relevant_candidate_change
- `example_029` `answer_shape_count` supportable_delta=0.0008 categories=['runtime_or_tool_gate'] reason=no_accuracy_relevant_candidate_change
- `example_028` `answer_shape_date` supportable_delta=0.0008 categories=['runtime_or_tool_gate'] reason=no_accuracy_relevant_candidate_change
- `example_031` `answer_shape_list` supportable_delta=0.0007 categories=['runtime_or_tool_gate'] reason=no_accuracy_relevant_candidate_change
- `example_030` `answer_shape_list` supportable_delta=0.0006 categories=['runtime_or_tool_gate'] reason=no_accuracy_relevant_candidate_change
- `example_019` `answer_shape_list` supportable_delta=0.0006 categories=['runtime_or_tool_gate'] reason=no_accuracy_relevant_candidate_change
- `example_029` `answer_only` supportable_delta=-0.0036 categories=['runtime_or_tool_gate', 'token_gate_failed'] reason=token_gate_failed
- `example_020` `answer_shape_count` supportable_delta=-0.007 categories=['runtime_or_tool_gate'] reason=no_accuracy_relevant_candidate_change; no_score_or_correctness_improvement
- `example_020` `answer_only` supportable_delta=-0.0168 categories=['runtime_or_tool_gate', 'token_gate_failed'] reason=token_gate_failed
- `example_019` `answer_only` supportable_delta=-0.0194 categories=['runtime_or_tool_gate', 'token_gate_failed'] reason=token_gate_failed
- `example_024` `dry_run_evidence_answer` supportable_delta=-0.0509 categories=['answer_drift', 'runtime_or_tool_gate'] reason=final_answer_unsafe_drift; no_score_or_correctness_improvement
