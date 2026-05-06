# score075 dry-run answer eval

Branch: `codex/score075-dryrun-answer`

## Summary

Implemented a default-off evidence-aware dry-run answer candidate behind `ENABLE_EVIDENCE_AWARE_DRY_RUN_ANSWERS=1`.

Default packaged behavior is unchanged because the flag defaults off and no config default was changed.

## Safety

- Dry-run `result_preview` is ignored as payload evidence.
- Values not present in SQL rows, selected request params, or query-visible text are reported as unavailable in dry-run mode.
- Secret-like request params are never echoed.
- No scorer logic changed.
- No hidden-style tests changed.
- No final-submission or official eval outputs were written.
- No gold SQL, gold API path, gold answer, query-id branch, or exact public query mapping was added.

## Tests

`python3 -m pytest tests/test_answer_correctness_layer.py`

Result: `11 passed`

`python3 -m pytest`

Result: `241 passed`

## Blocker

Local Parquet index evidence integration is blocked on the `codex/score075-local-index` worker defining the evidence-object contract. See `outputs/score075_dryrun_answer_handoff.md`.
