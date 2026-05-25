# External Text-to-SQL and Tool-Agent Research

This scan records external patterns that are relevant to DASHSys, but it does not copy code, add dependencies, or promote new runtime behavior.

- Recommendation: `Use external patterns as audit and candidate-ranking guidance only; do not add dependencies or promote LLM SQL/controller behavior in this pass.`

## Ideas

### Context7 /websites/sqlglot

- Source URL: https://sqlglot.com/sqlglot/optimizer/qualify.html
- Idea: Use SQLGlot parse, normalization, and table/column qualification as a deterministic validation and SQL-shape comparison layer.
- Relevance: High: DASHSys already uses read-only SQL validation; AST shape checks help detect unsafe or unstable candidate SQL without executing broad speculative queries.
- Risk: `low`
- Safe to implement now: `False`
- Decision: Keep as candidate for schema-aware/no-template SQL ranking, not a runtime promotion in this pass.

### Context7 /websites/vanna_ai

- Source URL: https://vanna.ai/docs/placeholder/audit-logging
- Idea: Maintain audit logs for tool invocations and results while sanitizing tool parameters and avoiding full sensitive response logging.
- Relevance: High: DASHSys trajectory/reporting can use compact audited tool summaries rather than repeated raw payload context.
- Risk: `medium`
- Safe to implement now: `False`
- Decision: Use only as design guidance for live API efficiency compression; no dependency or copied implementation.

### Context7 /websites/vanna_ai

- Source URL: https://vanna.ai/docs/placeholder/llm-context-enhancers
- Idea: Context/RAG enhancers should separate successful tool-use examples from failed attempts and keep them bounded.
- Relevance: Medium: generated prompts and controller traces can mine failures, but generated labels must remain diagnostic-only.
- Risk: `medium`
- Safe to implement now: `False`
- Decision: Do not add RAG memory; use failure clusters only for offline diagnostics.

### Context7 /defog-ai/sqlcoder

- Source URL: https://context7.com/defog-ai/sqlcoder/llms.txt
- Idea: LLM SQL generation should be treated as candidate generation from schema metadata, then validated before execution.
- Relevance: Medium: aligns with shadow-only schema-aware/LLM SQL candidate policy.
- Risk: `high`
- Safe to implement now: `False`
- Decision: Keep LLM SQL candidate generation shadow-only; no promotion without multi-backend and no-LLM gates.
