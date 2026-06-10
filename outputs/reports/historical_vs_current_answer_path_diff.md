# Historical vs Current Answer Path Diff

Key differences:

- Historical scorer gave empty generated answers 0.85 via substring match; current scorer blocks empty answer credit.
- Historical local high-score trajectories selected empty LLM output directly; current isolated strategy falls back to legacy/deterministic safe renderer.
- Historical generator only extracted top-level content or complete_json answer; current generator also handles OpenAI choices/message and output_text shapes.
- Current generator records backend availability, response shape, raw_response_ok, error-present boolean, extracted content length, and failure category.
- Current SQL_FIRST_LLM strategy preserves SQL/API tool path and changes only answer generation/selection.

Most likely current empty-generation cause: The active LLM client returned ok=false/error-present empty content for every organizer row; before instrumentation this collapsed to empty_llm_answer.
Old path safe to port: `False`

## Current Main Sanity Checks

- check_submission_ready: `ok=true`
- git diff --check: `pass`
- focused tests: `14 passed`
- packaged default unchanged: `SQL_FIRST_API_VERIFY`
- credential values printed: `false`
