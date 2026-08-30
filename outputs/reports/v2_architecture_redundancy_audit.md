# V2 Architecture Redundancy Audit

## Active V2 Path

`ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2` uses the Unified LLM Planner facade as the public planner boundary. The primary internal planning contract is SDK-native Semantic IR tool calling:

`run_llm_unified_planner` -> `submit_semantic_ir_plan` / micro Semantic IR tools -> Semantic IR parser -> Semantic IR validator -> Answer Contract validator -> schema repair-hint diagnostics -> Semantic IR support check -> optional LLM-owned repair -> mechanical SQL/API compiler -> SQLCompileGate/APIRequestGate -> execution -> ResultBundle/EvidenceBus -> LLM final answer composer -> final grounding/contract gates.

The backend validates exact table, field, endpoint, and graph shape choices. It does not choose replacement tables, endpoints, fields, filters, subtasks, SQL, API paths, or final answers.

## Legacy Paths

- `SQL_FIRST_API_VERIFY` remains the packaged default and baseline path.
- SQL_FIRST answer-layer experiments remain explicit-only and are not part of the V2 planner path.
- The older Unified Planner free-form SQL/API path is not the active V2 path.

## Diagnostic-Only Paths

- Planner-only diagnostics under `scripts/diagnose_deepseek_v2_planner_only.py`.
- Hermes/Qwen/DeepSeek smoke runners under `scripts/run_hermes_v2_toolcall_smoke.py`.
- SDK usage audit and local provider probes.
- Historical atomic weak protocol tests and reports.

## Fallback Paths

- Atomic/text protocol remains fallback/diagnostic for providers without tool-call capability, but current V2 SDK-toolcall smoke requires native tool calls and does not use text fallback.
- Raw SQL fallback is LLM-owned and only considered after supported Semantic IR repair fails for declared unsupported local query structure. The backend runs the raw SQL safety/compile gates but does not generate or repair SQL.
- Safe runtime fallback answers are allowed only after final answer syntax/semantic gates fail; they report evidence state and do not fabricate facts.

## Repair Paths

- Invalid Semantic IR shape, unknown table, unknown field, unknown endpoint, answer contract mismatch, support mismatch, dependency failure, SQL compile failure, and API request gate failure can trigger one LLM-owned repair where implemented.
- Repair prompts include compact table, field, endpoint, relationship, and role cards. The backend supplies catalog context only; the LLM remains responsible for the corrected plan.
- Schema-binding toolcall remains feature-flagged via `V2_ENABLE_SCHEMA_BINDING=1`. Default behavior uses repair-hint diagnostics rather than a separate schema-binding tool call.

## Feature-Flagged Components

- `submit_schema_binding_plan`: experimental toolcall path, gated by `V2_ENABLE_SCHEMA_BINDING`.
- Pioneer/Gemini/local-provider sweeps: provider diagnostics only, not default strategy.
- V2 execution optimizer/cache/checkpoint logic: backend-only scheduling/resource optimization; it must not change Semantic IR semantics.

## Redundant Or Deprecated Candidates

- Free-form planner payload fallback should remain non-primary and can be removed later after all required SDK-toolcall providers are stable.
- Atomic/text protocol artifacts should remain only for diagnostic coverage and weak-provider failure analysis.
- Historical answer-only SQL_FIRST hybrid/concise experiments should remain explicit-only and not merge into V2 planner routing.

## Current Stabilization Notes

- Local evidence source checks now reject API-only or DIRECT-only Semantic IR plans for schema and local date prompts that have no live/current/API cue, and return them to the LLM repair loop.
- DIRECT routes with required local/live answer-contract slots are rejected before execution.
- Answer-contract enum aliases are normalized to safe scoped policies to avoid malformed model strings causing parse-only failures.
- Smoke timing diagnostics clamp invisible time at zero and mark timing accounting errors when instrumented stage time exceeds total latency.

## Delete Later

No deletion is recommended in this pass. The current diff is stabilization-only, and the repo still needs the diagnostic paths to compare SDK-toolcall behavior across local and external OpenAI-compatible providers.
