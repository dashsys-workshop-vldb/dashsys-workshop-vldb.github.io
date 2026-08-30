# V2 Answer Contract Design

## Scope
- Strategy affected: `ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` only.
- Packaged default remains `SQL_FIRST_API_VERIFY`.
- Backend validates contract shape and evidence state; it does not infer answer slots or user intent.

## Modules
- `dashagent/v2_answer_contract.py`: Dataclasses and parser/serializer for LLM-owned answer contracts and evidence slot states.
- `dashagent/v2_answer_contract_validator.py`: Shape/reference/scope validator for answer contracts; no backend semantic inference.
- `dashagent/v2_evidence_contract.py`: Runtime evidence-state evaluator mapping pass results to required answer slots.
- `dashagent/final_answer_contract_gate.py`: Final answer gate that blocks unsupported positives, raw evidence dumps, and caveat misuse.

## Runtime Wiring
- SemanticIRValidator invokes AnswerContractValidator after existing task/table/API/alias validation.
- Compiled V2 plan carries answer_contract into the LLMUnifiedPlan-compatible payload.
- Executor evaluates evidence contract after ResultBundle construction.
- LLM final answer card receives answer_contract and evidence_slot_states.
- Final answer semantic gate is wrapped by FinalAnswerContractGate before existing grounding checks.

## Validation
- Focused V2 tests: 142 passed
- Full pytest: 1206 passed, 1 skipped
- check_submission_ready ok: True
- SDK direct HTTP hits: None
- git diff --check: passed
