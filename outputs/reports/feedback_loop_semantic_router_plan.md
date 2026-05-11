# Semantic Router Feedback Loop Plan

- Candidate: `LLM Semantic Routing Helper`
- Target stage: `Deterministic QueryRouter / QueryAnalysis semantic fallback`
- Baseline score: `0.6553`
- Prior broad variant strict delta: `-0.0031`
- Prior conclusion: The first broad non-shadow semantic-router variant regressed; this does not disprove the entire semantic-router idea.

## Variants

- Iteration 1: `narrow_eligibility` - The first broad non-shadow semantic-router variant regressed; narrower eligibility may preserve useful fallback behavior while avoiding high-confidence perturbations.
- Iteration 2: `no_intent_application` - The first trial changed intent metadata without improving SQL/API/answer; recording intent but not applying it may remove noise.
- Iteration 3: `priority_only` - Validated semantic hints may be useful as table/API priority signals without changing route, domain, or intent.
- Iteration 4: `unknown_only` - The helper may be safest as a true fallback only when deterministic routing cannot identify a domain.
- Iteration 5: `no_api_forcing` - Dry-run API behavior may hurt answers; semantic hints should not force API routes unless the existing route already expects API evidence.
