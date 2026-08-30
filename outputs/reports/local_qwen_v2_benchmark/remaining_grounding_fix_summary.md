# Remaining Grounding Fix Summary

Generated: 2026-06-02T14:05:13.155528+00:00

## Objective Result

The narrow answer-grounding pass reduced the original non-timeout final semantic gate failures from 8 to 2. The remaining non-timeout failures are `example_012, example_021`. `example_003` remains a contained timeout and is not counted as a final answer grounding failure.

## Fixes Applied

- Status claim extractor now suppresses negative/unavailable status-context false positives without ignoring status claims globally.
- Safe fallback receives AnswerSlots and preserves requested status/filter labels for zero-row local evidence.
- Missing-required-fields gate no longer requires prompt-only fields when all required runtime evidence failed and final answer is a scoped runtime/API unavailable caveat.
- Most-recent ranked summary gate allows concise top-entity-plus-timestamp answers when timestamp evidence is present.

## Fresh Eval Metrics

|Rows|Timeouts|Timeout IDs|Final Gate Failures|Failure Counts|SQL Calls|API Calls|Tool Calls|Final Unsupported Rows|No-tool FP|Raw SQL Fallback|Pass Results|Successful Pass Results|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|35|1|["example_003"]|2|{"missing_required_info": 2}|22|25|47|0|0|0|51|16|

## Raw Score Only

|Final|Correctness|Answer|SQL|API|Runtime|Tokens|Tool Calls|
|---|---|---|---|---|---|---|---|
|0.2184|0.2717|0.1961|0.0|0.4537|11.7216|2074.4857|1.3429|

## Remaining Blockers

- example_003 still times out in the LLM-owned dependency-resolution path.
- example_012 still fails true missing_required_info for segment audience to destination mapping detail.
- example_021 still fails true missing_required_info for default merge policy relation.
- example_004 now passes the gate but still has objective answer-quality risk because enabled dataflow run examples are surfaced for a failed-runs prompt; this appears upstream/evidence-selection related and was not changed in this narrow pass.

## Recommendation

Safe to keep and commit the narrow answer-grounding/test/report changes. Not safe to promote V2: the V2 path still has one contained timeout and two real non-timeout missing-information failures.
