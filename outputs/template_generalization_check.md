# Template Generalization Check

| Template | Family | Uses | Schema/API Validated | Risk | Recommended Action |
|---|---|---|---|---|---|
| journey_campaign_* | journey_campaign | dim_campaign; GET /ajo/journey | True | low | Keep: Entity names are extracted from quotes or status keywords. |
| segment_destination_relationship | segment_audience | dim_segment + hkg_br_segment_target + dim_target; audience/flow APIs | True | low | Keep: Schema-validated bridge join. |
| segment_new_destination_mapping | audit | segment-target bridge and audit events | True | medium | Monitor on hidden queries: Uses reusable relative-time pattern from query family. |
| destination_export_recent | destination_dataflow | dim_target; flowservice flows | True | low | Keep: Projection is schema-derived; LIMIT kept unless explicit no-limit request appears. |
| blueprint_collection_* | schema_dataset | dim_blueprint + dim_collection bridge | True | low | Keep: Reusable schema/dataset aggregation and detail templates. |
| segment_property_fields | property_field | hkg_br_segment_property + dim_segment | True | low | Keep: Segment name is extracted from the query. |
| audit_create_events | audit | GET /data/foundation/audit/events | True | low | Keep: Reusable action=create audit filter. |
| merge_policies | merge_policy | GET /data/core/ups/config/mergePolicies | True | low | Keep: No default policy value is invented in dry-run mode. |
| tag_* | tags | unified tags APIs | True | medium | Monitor on hidden queries: Named tag detail uses benchmark-compatible ID fallback only when no tag ID is present. |
| observability_metrics | observability | POST observability metrics | True | low | Keep: Metric names and date windows are extracted from query text. |
| answer_templates | answer | SQL/API tool evidence | True | low | Keep: Templates render observed fields only and report dry-run limitations. |
| query_normalizer | nlp | Whitespace, quote, hyphen, synonym, and plural normalization | True | low | Keep: Normalized text is used only for matching; original query is preserved in outputs. |
| query_tokens | nlp | Quoted/named entities, IDs, dates, metrics, fields, statuses, domain tokens | True | low | Keep: Extracted tokens guide deterministic selection without external embeddings. |
| relevance_scorer | nlp | Token overlap, lookup-path weights, optional RapidFuzz | True | low | Keep: Scores compact schema/API context; it does not bypass SQL/API validation. |
| plan_ensemble | planning | Pre-execution candidate scoring over validated deterministic plans | True | low | Keep: Only the selected plan is executed; candidate evaluation is validation-only. |
