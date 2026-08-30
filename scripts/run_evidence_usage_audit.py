#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.answer_claims import extract_availability_claims, extract_claims
from dashagent.answer_faithfulness import evaluate_answer_faithfulness
from dashagent.answer_intent import classify_answer_intent
from dashagent.answer_slots import extract_answer_slots
from dashagent.config import Config
from dashagent.report_run import report_metadata
from dashagent.trajectory import redact_secrets
from scripts.run_evidence_aware_answer_rewrite_trial import tool_results_from_trajectory
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


CATEGORIES = {
    "evidence_used_well",
    "answer_too_vague",
    "answer_missing_count",
    "answer_missing_names",
    "answer_missing_status",
    "answer_missing_timestamp",
    "answer_overmentions_dry_run",
    "answer_confuses_live_empty_with_dry_run",
    "unsupported_claim",
    "evidence_available_but_unused",
    "zero_row_answer_unclear",
    "list_answer_shape_weak",
    "count_answer_shape_weak",
    "status_answer_shape_weak",
    "date_answer_shape_weak",
    "api_error_answer_shape_weak",
    "no_clear_answer_issue",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_evidence_usage_audit(config)
    print(json.dumps({"status": payload["status"], "rows": payload["total_rows"]}, indent=2, sort_keys=True))
    return 0


def run_evidence_usage_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = [_audit_row(row) for row in strict.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY"]
    distribution = dict(Counter(row["primary_issue_category"] for row in rows))
    payload = {
        **report_metadata(config.outputs_dir),
        "report_type": "evidence_usage_audit",
        "status": "complete" if rows else "skipped",
        "official_score_claim": False,
        "total_rows": len(rows),
        "category_distribution": distribution,
        "summary": {
            "unsupported_claim_rows": sum(1 for row in rows if row["unsupported_claim_count"] > 0),
            "dry_run_caveat_rows": sum(1 for row in rows if row["dry_run_caveat_presence"]),
            "evidence_available_but_unused_rows": distribution.get("evidence_available_but_unused", 0),
            "answer_shape_weak_rows": sum(
                distribution.get(name, 0)
                for name in [
                    "list_answer_shape_weak",
                    "count_answer_shape_weak",
                    "status_answer_shape_weak",
                    "date_answer_shape_weak",
                    "api_error_answer_shape_weak",
                ]
            ),
        },
        "rows": rows,
    }
    _write_report(reports_dir / "evidence_usage_audit", payload, _render(payload))
    return payload


def _audit_row(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = _load_trajectory(row.get("output_dir"))
    query = str(row.get("query") or trajectory.get("original_query") or "")
    answer = str(trajectory.get("final_answer") or "")
    tool_results = tool_results_from_trajectory(trajectory)
    slots = extract_answer_slots(query, tool_results)
    faith = evaluate_answer_faithfulness(answer, slots)
    claims = [claim.__dict__ for claim in extract_claims(answer) + extract_availability_claims(answer)]
    first_sentence = answer.split(".")[0].strip() + ("." if "." in answer else "")
    category = _categorize(answer, slots, faith)
    evidence_fields = slots.compact()
    return redact_secrets(
        {
            "query_id": row.get("query_id"),
            "prompt": query,
            "route_type": trajectory.get("route_type"),
            "domain_type": trajectory.get("domain_type"),
            "answer_family": slots.answer_family,
            "answer_intent": str(classify_answer_intent(query, slots)),
            "sql_evidence_available": bool(slots.first_rows or slots.sql_row_count is not None),
            "api_evidence_available": bool(slots.api_items or slots.live_api_evidence_available),
            "parsed_evidence_available": any(
                isinstance((result.get("payload") or {}).get("parsed_evidence"), dict)
                for result in tool_results
                if result.get("type") == "api"
            ),
            "evidence_bus_extracted_fields": _evidence_bus_fields(trajectory),
            "answer_slots": evidence_fields,
            "final_answer": answer,
            "final_answer_first_sentence": first_sentence,
            "final_answer_claims": claims,
            "supported_claim_count": len(faith.supported_claims),
            "unsupported_claim_count": len(faith.unsupported_claims),
            "unused_evidence_fields": faith.unused_evidence,
            "dry_run_caveat_presence": bool(slots.dry_run and ("credential" in answer.lower() or "unavailable" in answer.lower())),
            "answer_directness_score": _directness_score(answer, slots),
            "answer_faithfulness_score": faith.faithfulness_score,
            "answer_relevance_score": _relevance_score(faith),
            "strict_answer_score": row.get("answer_score"),
            "primary_issue_category": category,
            "valid_categories": sorted(CATEGORIES),
        }
    )


def _categorize(answer: str, slots: Any, faith: Any) -> str:
    lowered = answer.lower()
    if faith.unsupported_claims:
        return "unsupported_claim"
    if slots.api_evidence_state in {"live_empty", "live_empty_result"} and "credential" in lowered:
        return "answer_confuses_live_empty_with_dry_run"
    if slots.api_error and "failed" not in lowered and "error" not in lowered:
        return "api_error_answer_shape_weak"
    if slots.sql_row_count == 0 and not any(token in lowered for token in ["no matching", "no rows", "returned no"]):
        return "zero_row_answer_unclear"
    if slots.dry_run and lowered.count("dry") + lowered.count("credential") > 2:
        return "answer_overmentions_dry_run"
    unused = set(faith.unused_evidence)
    if "counts" in unused:
        return "answer_missing_count"
    if "names" in unused:
        return "answer_missing_names"
    if "statuses" in unused:
        return "answer_missing_status"
    if "timestamps" in unused:
        return "answer_missing_timestamp"
    if unused:
        return "evidence_available_but_unused"
    if _directness_score(answer, slots) < 0.5:
        return "answer_too_vague"
    return "evidence_used_well"


def _evidence_bus_fields(trajectory: dict[str, Any]) -> dict[str, Any]:
    for checkpoint in trajectory.get("checkpoints", []):
        if checkpoint.get("checkpoint_id") == "checkpoint_14_evidence_bus":
            output = checkpoint.get("output") if isinstance(checkpoint.get("output"), dict) else {}
            evidence = output.get("evidence") if isinstance(output, dict) else {}
            if isinstance(evidence, dict):
                return {
                    "ids": evidence.get("ids"),
                    "names": evidence.get("names"),
                    "counts": evidence.get("counts"),
                    "statuses": evidence.get("statuses"),
                    "timestamps": evidence.get("timestamps"),
                    "errors": evidence.get("api_errors") or evidence.get("errors"),
                    "pagination": evidence.get("api_pagination"),
                    "evidence_state": evidence.get("api_evidence_states"),
                    "evidence_source": evidence.get("api_evidence_sources") or evidence.get("sources"),
                }
    return {}


def _directness_score(answer: str, slots: Any) -> float:
    first = answer.split(".")[0].lower()
    if slots.counts and any(str(value).lower() in first for value in slots.counts):
        return 1.0
    if slots.entity_names and any(str(value).lower() in first for value in slots.entity_names[:3]):
        return 1.0
    if slots.statuses and any(str(value).lower() in first for value in slots.statuses[:3]):
        return 1.0
    if slots.timestamps and any(str(value).lower()[:10] in first for value in slots.timestamps[:3]):
        return 1.0
    if first.startswith(("you have", "matching", "yes", "no", "live api returned", "the sql query returned")):
        return 0.8
    return 0.4


def _relevance_score(faith: Any) -> float:
    penalty = min(0.6, 0.15 * len(faith.unused_evidence))
    if faith.answer_relevance_flags:
        penalty += min(0.3, 0.1 * len(faith.answer_relevance_flags))
    return round(max(0.0, faith.faithfulness_score - penalty), 4)


def _write_report(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# Evidence Usage Audit",
        "",
        "Report-only audit of whether final answers use available SQL/API evidence. No runtime behavior changed.",
        "",
        f"- Status: `{payload['status']}`",
        f"- Rows: `{payload['total_rows']}`",
        f"- Official score claim: `{payload['official_score_claim']}`",
        "",
        "## Category Distribution",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(payload["category_distribution"].items()))
    lines.extend(["", "## Examples", ""])
    for row in payload.get("rows", [])[:8]:
        lines.append(f"- `{row['query_id']}` {row['primary_issue_category']}: {row['final_answer_first_sentence']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
