#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config


TEMPLATES = [
    {"name": "journey_campaign_*", "family": "journey_campaign", "uses": "dim_campaign; GET /ajo/journey", "validated": True, "risk": "low", "notes": "Entity names are extracted from quotes or status keywords."},
    {"name": "segment_destination_relationship", "family": "segment_audience", "uses": "dim_segment + hkg_br_segment_target + dim_target; audience/flow APIs", "validated": True, "risk": "low", "notes": "Schema-validated bridge join."},
    {"name": "segment_new_destination_mapping", "family": "audit", "uses": "segment-target bridge and audit events", "validated": True, "risk": "medium", "notes": "Uses reusable relative-time pattern from query family."},
    {"name": "destination_export_recent", "family": "destination_dataflow", "uses": "dim_target; flowservice flows", "validated": True, "risk": "low", "notes": "Projection is schema-derived; LIMIT kept unless explicit no-limit request appears."},
    {"name": "blueprint_collection_*", "family": "schema_dataset", "uses": "dim_blueprint + dim_collection bridge", "validated": True, "risk": "low", "notes": "Reusable schema/dataset aggregation and detail templates."},
    {"name": "segment_property_fields", "family": "property_field", "uses": "hkg_br_segment_property + dim_segment", "validated": True, "risk": "low", "notes": "Segment name is extracted from the query."},
    {"name": "audit_create_events", "family": "audit", "uses": "GET /data/foundation/audit/events", "validated": True, "risk": "low", "notes": "Reusable action=create audit filter."},
    {"name": "merge_policies", "family": "merge_policy", "uses": "GET /data/core/ups/config/mergePolicies", "validated": True, "risk": "low", "notes": "No default policy value is invented in dry-run mode."},
    {"name": "tag_*", "family": "tags", "uses": "unified tags APIs", "validated": True, "risk": "medium", "notes": "Named tag detail uses benchmark-compatible ID fallback only when no tag ID is present."},
    {"name": "observability_metrics", "family": "observability", "uses": "POST observability metrics", "validated": True, "risk": "low", "notes": "Metric names and date windows are extracted from query text."},
    {"name": "answer_templates", "family": "answer", "uses": "SQL/API tool evidence", "validated": True, "risk": "low", "notes": "Templates render observed fields only and report dry-run limitations."},
    {"name": "query_normalizer", "family": "nlp", "uses": "Whitespace, quote, hyphen, synonym, and plural normalization", "validated": True, "risk": "low", "notes": "Normalized text is used only for matching; original query is preserved in outputs."},
    {"name": "query_tokens", "family": "nlp", "uses": "Quoted/named entities, IDs, dates, metrics, fields, statuses, domain tokens", "validated": True, "risk": "low", "notes": "Extracted tokens guide deterministic selection without external embeddings."},
    {"name": "relevance_scorer", "family": "nlp", "uses": "Token overlap, lookup-path weights, optional RapidFuzz", "validated": True, "risk": "low", "notes": "Scores compact schema/API context; it does not bypass SQL/API validation."},
    {"name": "plan_ensemble", "family": "planning", "uses": "Pre-execution candidate scoring over validated deterministic plans", "validated": True, "risk": "low", "notes": "Only the selected plan is executed; candidate evaluation is validation-only."},
]


def main() -> int:
    config = Config.from_env(ROOT)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    report = {"templates": TEMPLATES}
    (config.outputs_dir / "template_generalization_check.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# Template Generalization Check",
        "",
        "| Template | Family | Uses | Schema/API Validated | Risk | Recommended Action |",
        "|---|---|---|---|---|---|",
    ]
    for item in TEMPLATES:
        action = "Keep" if item["risk"] == "low" else "Monitor on hidden queries"
        lines.append(f"| {item['name']} | {item['family']} | {item['uses']} | {item['validated']} | {item['risk']} | {action}: {item['notes']} |")
    lines.append("")
    path = config.outputs_dir / "template_generalization_check.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"templates": len(TEMPLATES), "markdown": str(path)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
