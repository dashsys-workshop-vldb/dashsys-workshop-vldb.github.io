# Pure LLM Improvement Scope

Diagnostic-only scope. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.

## Allowed

- LLM-driven planning
- LLM-generated structured SQL intent
- LLM endpoint choice from catalog
- dynamic schema/context retrieval
- dynamic few-shot retrieval from non-gold examples
- validator feedback
- SQL repair loop
- execution probe
- evidence-grounded answer

## Not Allowed

- packaged deterministic planner as hidden backend
- query-specific or gold-specific templates
- hard-coded public/dev answers
- bypassing validators
- answer fabrication
