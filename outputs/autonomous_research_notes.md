# Autonomous Research Notes

- Web access available: True
- Worker branch: `codex/score075-dryrun-answer`

| Technique | Source | Decision | Result |
|---|---|---|---|
| Eval-driven regression gates | https://platform.openai.com/docs/guides/evaluation-best-practices | implemented | Encoded as promotion gates and integration validation protocol. |
| CHASE-SQL multi-path candidate generation and selection | https://arxiv.org/abs/2410.01943 | implemented_as_gated_scaffolding | Candidate generation and execution selector branches are isolated and blocked behind validation. |
| CHESS schema/value retrieval and schema pruning | https://arxiv.org/pdf/2405.16755 | implemented_as_candidate_direction | Assigned to local-index, endpoint-routing, and candidate-generation workers. |
| DIN-SQL task decomposition and self-correction | https://arxiv.org/abs/2304.11015 | implemented_as_report_scaffolding | Improvement backlog separates targeted failure types and worker ownership. |
| DAIL-SQL prompt/example organization | https://arxiv.org/abs/2308.15363 | partially_rejected | No runtime few-shot public-example mechanism is added by coordinator. |
| RSL-SQL robust schema linking | https://arxiv.org/abs/2411.00073 | implemented_as_gate | Hidden-style 48/48 and no reduced candidate diversity are merge requirements. |
| Execution-guided SQL generation | https://arxiv.org/abs/1807.03100 | implemented_as_gated_scaffolding | Assigned to execution selector and autonomous packaged trial workflow. |
| SQLGlot AST validation | https://sqlglot.com/sqlglot.html | implemented_as_gate | Included in worker and selector safety requirements. |

## Guardrails

- Sources are used to guide offline candidate generation and validation only.
- No external source is used to justify gold/public-query memorization.
