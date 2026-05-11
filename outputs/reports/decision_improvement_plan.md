# Decision Improvement Plan

- Selected decision stage: `Answer synthesis / Evidence policy`
- Implemented in this diff: `False`
- Why: Answer-only rewrite or dry-run wording/API optional skip, because workflow audit often marks answer_shape_weak or unnecessary_dry_run_api while SQL/API evidence is already present.
- Safety risk: Answer-only variants must preserve SQL/API/tool/evidence/dry-run hashes; API-skip variants must remain isolated.
- Rollback condition: Any SQL/API/tool/evidence/dry-run hash change for answer-only trials or any strict/readiness/security regression.
