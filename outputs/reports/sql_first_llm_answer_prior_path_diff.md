# SQL_FIRST LLM Answer Prior Path Diff

- Prior trajectories found: `35`
- Prior empty final answers: `35`
- Answer payload gold/category/tags/oracle/expected-trace leakage found: `True`
- Prior path status: `runtime_payload_clean_but_score_inflated_by_empty_answer_evaluator_bug`
- Module/function: `dashagent.evidence_grounded_llm_answer_generator.generate_evidence_grounded_llm_answer`

## Finding

The prior high-scoring ablation selected evidence_grounded_llm_answer_generator output directly and allowed an empty final answer to pass verification; strict scoring then gave empty generated answers 0.85 because empty string matched as a substring of gold. The isolated SQL_FIRST strategy uses answer_candidate_selector fallback, so empty LLM output does not become final answer.

Reuse decision: `do_not_reuse_prior_empty_answer_selection; keep selector/verifier fallback and strict scorer empty-answer guard`
