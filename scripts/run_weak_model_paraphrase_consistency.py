#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets

REPORT_STEM = "weak_model_paraphrase_consistency"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_weak_model_paraphrase_consistency(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_model_paraphrase_consistency(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    source = reports / "weak_model_generated_prompt_diagnostic.json"
    generated = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {"rows": []}
    rows = [row for row in generated.get("rows", []) if row.get("runtime_pass")]
    groups = _build_groups(rows)
    summary = _summary(groups)
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "source_report": str(source),
            "summary": summary,
            "groups": groups,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _build_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("source_group_id") or row.get("source_prompt") or row.get("prompt_id")), []).append(row)
    groups = []
    for group_id, items in sorted(grouped.items()):
        if len(items) < 2:
            continue
        fields = {
            "slot_signature": [_slot_signature(row) for row in items],
            "evidence_need": [row.get("evidence_need") for row in items],
            "selected_sql_table": [row.get("selected_sql_table") for row in items],
            "endpoint_selected": [row.get("endpoint_selected") for row in items],
            "answer_intent": [row.get("answer_intent") for row in items],
            "answer_grounding": [_answer_grounding(row) for row in items],
        }
        stability = {name: _stable(values) for name, values in fields.items()}
        consistency = round(sum(stability.values()) / len(stability), 4)
        groups.append(
            {
                "group_id": group_id,
                "prompt_count": len(items),
                "prompts": [row.get("prompt") for row in items],
                "slot_stability": stability["slot_signature"],
                "evidence_need_stability": stability["evidence_need"],
                "sql_table_stability": stability["selected_sql_table"],
                "api_endpoint_stability": stability["endpoint_selected"],
                "answer_intent_stability": stability["answer_intent"],
                "answer_grounding_stability": stability["answer_grounding"],
                "consistency_score": consistency,
                "unstable_fields": [name for name, value in stability.items() if value < 1.0],
                "field_values": fields,
            }
        )
    return groups


def _summary(groups: list[dict[str, Any]]) -> dict[str, Any]:
    if not groups:
        return {
            "group_count": 0,
            "consistency_score": 0.0,
            "slot_stability": 0.0,
            "sql_table_stability": 0.0,
            "api_endpoint_stability": 0.0,
            "answer_grounding_stability": 0.0,
            "worst_unstable_groups": [],
        }
    return {
        "group_count": len(groups),
        "consistency_score": _avg(groups, "consistency_score"),
        "slot_stability": _avg(groups, "slot_stability"),
        "sql_table_stability": _avg(groups, "sql_table_stability"),
        "api_endpoint_stability": _avg(groups, "api_endpoint_stability"),
        "answer_intent_stability": _avg(groups, "answer_intent_stability"),
        "answer_grounding_stability": _avg(groups, "answer_grounding_stability"),
        "unstable_field_counts": dict(Counter(field for group in groups for field in group.get("unstable_fields", []))),
        "worst_unstable_groups": sorted(
            [{"group_id": group["group_id"], "consistency_score": group["consistency_score"], "unstable_fields": group["unstable_fields"]} for group in groups],
            key=lambda item: float(item["consistency_score"]),
        )[:10],
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    worst = "\n".join(f"- `{item['group_id']}`: `{item['consistency_score']}` ({', '.join(item['unstable_fields'])})" for item in summary.get("worst_unstable_groups", []))
    return (
        "# Weak Model Paraphrase Consistency\n\n"
        "Diagnostic-only consistency check over the weak generated-prompt diagnostic rows.\n\n"
        f"- Groups: `{summary.get('group_count')}`\n"
        f"- Consistency score: `{summary.get('consistency_score')}`\n"
        f"- Slot stability: `{summary.get('slot_stability')}`\n"
        f"- SQL table stability: `{summary.get('sql_table_stability')}`\n"
        f"- API endpoint stability: `{summary.get('api_endpoint_stability')}`\n"
        f"- Answer grounding stability: `{summary.get('answer_grounding_stability')}`\n\n"
        "## Worst Unstable Groups\n\n"
        f"{worst}\n"
    )


def _slot_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    slots = row.get("semantic_slots") if isinstance(row.get("semantic_slots"), dict) else {}
    filters = slots.get("filters") if isinstance(slots.get("filters"), list) else []
    filter_sig = tuple(sorted((str(item.get("semantic_field")), str(item.get("operator"))) for item in filters if isinstance(item, dict)))
    return (row.get("answer_intent"), slots.get("domain"), row.get("evidence_need"), slots.get("aggregation"), filter_sig)


def _answer_grounding(row: dict[str, Any]) -> str:
    return f"sql={bool(row.get('answer_used_sql_evidence'))}|api={bool(row.get('answer_used_api_evidence'))}"


def _stable(values: list[Any]) -> float:
    normalized = {json.dumps(value, sort_keys=True, default=str) for value in values}
    return 1.0 if len(normalized) <= 1 else 0.0


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row.get(key) or 0.0) for row in rows]
    return round(sum(values) / len(values), 4) if values else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
