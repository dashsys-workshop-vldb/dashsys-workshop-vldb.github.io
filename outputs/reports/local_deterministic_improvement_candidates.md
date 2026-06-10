# Local Deterministic Improvement Candidates

Diagnostic-only candidate report. No runtime changes are applied by this report.

- Implementation-ready count: `0`
- No safe deterministic improvement applied: `True`
- Runtime change applied: `False`

## Candidates

- `route_mismatch:schema_dataset` ready=`False` count=`29` reason=depends on live Adobe API success, which is currently blocked
- `route_mismatch:destination_flow` ready=`False` count=`15` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `route_mismatch:segment_audience` ready=`False` count=`14` reason=depends on live Adobe API success, which is currently blocked
- `route_mismatch:journey_campaign` ready=`False` count=`9` reason=depends on live Adobe API success, which is currently blocked
- `route_mismatch:dataflow_run` ready=`False` count=`9` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `route_mismatch:observability` ready=`False` count=`8` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `route_mismatch:tags` ready=`False` count=`1` reason=fewer than 3 repeated examples
- `route_mismatch:unknown` ready=`False` count=`1` reason=fewer than 3 repeated examples
- `domain_mismatch:schema_dataset` ready=`False` count=`57` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `domain_mismatch:batch` ready=`False` count=`31` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `domain_mismatch:tags` ready=`False` count=`23` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `domain_mismatch:destination_flow` ready=`False` count=`22` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `domain_mismatch:dataflow_run` ready=`False` count=`17` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `domain_mismatch:merge_policy` ready=`False` count=`16` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `domain_mismatch:observability` ready=`False` count=`9` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `domain_mismatch:segment_audience` ready=`False` count=`1` reason=fewer than 3 repeated examples
- `domain_mismatch:unknown` ready=`False` count=`1` reason=fewer than 3 repeated examples
- `answer_intent_mismatch:schema_dataset` ready=`False` count=`38` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `answer_intent_mismatch:segment_audience` ready=`False` count=`21` reason=diagnostic-only proposal; requires manual evidence review before implementation
- `answer_intent_mismatch:destination_flow` ready=`False` count=`20` reason=diagnostic-only proposal; requires manual evidence review before implementation

## Recommended Next Human Review

- Gap type: `requires_live_api`
- Why: Highest-volume advisory gap; review representative examples before considering deterministic rules.
- Generated prompts remain diagnostic-only; this report does not authorize runtime changes.
