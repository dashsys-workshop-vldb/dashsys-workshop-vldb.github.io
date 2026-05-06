# score075 dry-run answer handoff

Worker: `codex/score075-dryrun-answer`

Dependency: `codex/score075-local-index`

This branch implements evidence-aware dry-run answer candidates from currently recorded evidence only:

- SQL result rows
- selected dry-run request family and safe request params
- query-visible entity text, IDs, dates, and status words

Local Parquet index integration is intentionally not implemented in this branch because the local-index evidence object contract belongs to the local-index worker.

Requested local-index contract for later integration:

- return evidence objects, not final answers
- include a provenance field such as `parquet_table`, `column`, and `lookup_rule_id`
- include a classification such as `reusable_entity_lookup`, `reusable_value_grounding`, or `reusable_schema_relation_lookup`
- never include query-id, exact public query string, gold SQL/API path, or memorized answer provenance
- make unavailable fields explicit rather than implying live API payload evidence
