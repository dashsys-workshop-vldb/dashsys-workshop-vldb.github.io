# Weak Model Answer Grounding Harness

- Best variant: `weak_harness_full_v1`
- Best answer score: `0.2188`
- Answer non-regression: `False`

- SQL evidence is rendered when it directly answers the prompt.
- API evidence is rendered when required by evidence_need.
- SQL and API evidence are combined only when both add useful evidence.
- Unsupported claims remain rejected.
