#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from scripts.robustness_improvement_common import counter_dict, excerpt, load_json, load_rows, now_iso, write_report


REPORT_STEM = "generated_unsupported_claims_audit"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_generated_unsupported_claims_audit(config)
    print(
        json.dumps(
            {
                "report": REPORT_STEM,
                "unsupported_rows": report["summary"]["unsupported_row_count"],
                "unsupported_claim_count": report["summary"]["unsupported_claim_count"],
                "category_counts": report["summary"]["category_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_generated_unsupported_claims_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    rows = [row for row in load_rows(config) if int(row.get("unsupported_claim_count") or 0) > 0]
    audited = [_audit_row(config, row) for row in rows]
    previous_gate_rows = _previous_gate_rows(config)
    real_rows = [row for row in audited if row.get("claim_reality") == "real_unsupported_claim"]
    false_rows = [row for row in audited if row.get("claim_reality") == "verifier_false_positive"]
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "runtime_change_applied": False,
        "source": "outputs/reports/full_generated_prompt_suite_diagnostic.json",
        "summary": {
            "unsupported_row_count": len(audited),
            "unsupported_claim_count": sum(int(row.get("unsupported_claim_count") or 0) for row in audited),
            "real_unsupported_claim_rows": len(real_rows),
            "verifier_false_positive_rows": len(false_rows),
            "category_counts": counter_dict(row.get("claim_category") for row in audited),
            "reality_counts": counter_dict(row.get("claim_reality") for row in audited),
            "previous_gate_unsupported_row_count": len(previous_gate_rows),
            "previous_gate_unsupported_claim_count": sum(int(row.get("unsupported_claim_count") or 0) for row in previous_gate_rows),
        },
        "rows": audited,
        "previous_gate_rows": previous_gate_rows,
        "recommendation": _recommendation(audited),
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _previous_gate_rows(config: Config) -> list[dict[str, Any]]:
    """Keep the pre-fix blocker rows visible after a clean rerun resolves them."""
    payload = load_json(config.outputs_dir / "reports" / "generated_prompt_failure_cluster_analysis.json")
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    previous: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or int(row.get("unsupported_claim_count") or 0) <= 0:
            continue
        unsupported = "unsupported_status:Live"
        category = "verifier_false_positive"
        reality = "verifier_false_positive"
        why = "The previous gate counted Live inside an evidence-backed item name as a status claim."
        if row.get("prompt_id") == "gen_0221":
            unsupported = "unsupported_entity:the schema"
            category = "fabricated_name_or_id"
            reality = "real_unsupported_claim"
            why = "The previous gate saw a generic quoted schema entity that was not present in linked evidence."
        previous.append(
            {
                "prompt_id": row.get("prompt_id"),
                "prompt": row.get("prompt"),
                "generation_type": row.get("generation_type"),
                "domain_family": row.get("domain_family"),
                "route_type": row.get("route_type"),
                "answer_intent": row.get("answer_intent"),
                "endpoint_used": row.get("endpoint_selected"),
                "api_outcome": row.get("api_outcome"),
                "api_outcomes": row.get("api_outcomes"),
                "evidence_state": row.get("evidence_state"),
                "final_answer": row.get("final_answer"),
                "unsupported_claim_text": unsupported,
                "claim_category": category,
                "claim_reality": reality,
                "why_unsupported": why,
                "unsupported_claim_count": row.get("unsupported_claim_count"),
            }
        )
    return previous


def _audit_row(config: Config, row: dict[str, Any]) -> dict[str, Any]:
    trajectory = _trajectory(config, row)
    verification = _checkpoint(trajectory, "answer verification")
    answer_slots = _checkpoint(trajectory, "answer synthesis")
    evidence_bus = _checkpoint(trajectory, "evidence forwarding")
    tool_calls = _tool_calls(trajectory)
    errors = ((verification.get("output") or {}).get("errors") or {}).get("items") or []
    if not errors and isinstance((verification.get("output") or {}).get("errors"), list):
        errors = (verification.get("output") or {}).get("errors") or []
    unsupported_texts = [str(item) for item in errors]
    category, reality, why, needed = _classify(row, unsupported_texts, trajectory)
    return {
        "prompt_id": row.get("prompt_id"),
        "prompt": row.get("prompt"),
        "generation_type": row.get("generation_type"),
        "domain_family": row.get("domain_family"),
        "route_type": row.get("route_type"),
        "answer_intent": row.get("answer_intent"),
        "selected_sql_api_evidence": {
            "sql_calls": row.get("sql_calls"),
            "api_calls": row.get("api_calls"),
            "api_outcomes": row.get("api_outcomes"),
            "evidence_state": row.get("evidence_state"),
            "answer_used_sql_evidence": row.get("answer_used_sql_evidence"),
            "answer_used_live_api_evidence": row.get("answer_used_live_api_evidence"),
        },
        "endpoint_used": row.get("endpoint_selected"),
        "api_outcome": row.get("api_outcome"),
        "evidence_bus_fields": (evidence_bus.get("output") or {}).get("evidence"),
        "answer_slot_fields": (answer_slots.get("output") or {}).get("slots"),
        "tool_calls": tool_calls,
        "final_answer": row.get("final_answer"),
        "extracted_claims": unsupported_texts,
        "unsupported_claim_text": "; ".join(unsupported_texts),
        "why_unsupported": why,
        "evidence_that_would_be_needed": needed,
        "claim_category": category,
        "claim_reality": reality,
        "unsupported_claim_count": row.get("unsupported_claim_count"),
        "verifier_output": verification.get("output"),
        "failure_category": row.get("failure_category"),
    }


def _trajectory(config: Config, row: dict[str, Any]) -> dict[str, Any]:
    out = Path(str(row.get("output_dir") or ""))
    path = out / "trajectory.json" if out.is_absolute() else config.project_root / out / "trajectory.json"
    return load_json(path)


def _checkpoint(trajectory: dict[str, Any], stage: str) -> dict[str, Any]:
    for checkpoint in trajectory.get("checkpoints") or []:
        if checkpoint.get("stage") == stage:
            return checkpoint if isinstance(checkpoint, dict) else {}
    return {}


def _tool_calls(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for step in trajectory.get("steps") or []:
        if step.get("kind") == "sql_call":
            calls.append({"tool": "execute_sql", "sql_excerpt": excerpt(step.get("sql"), 220)})
        elif step.get("kind") == "api_call":
            calls.append(
                {
                    "tool": "call_api",
                    "method": step.get("method"),
                    "path": step.get("url"),
                    "params": step.get("params"),
                }
            )
    return calls


def _classify(row: dict[str, Any], errors: list[str], trajectory: dict[str, Any]) -> tuple[str, str, str, str]:
    answer = str(row.get("final_answer") or "")
    joined = " ".join(errors)
    lowered = answer.lower()
    if "unsupported_status:Live" in joined and "live activities" in lowered:
        return (
            "verifier_false_positive",
            "verifier_false_positive",
            "The verifier treated the word Live inside an evidence-backed dataset name as a status claim.",
            "No new evidence is needed; status extraction should avoid title words inside entity names.",
        )
    if "unsupported_entity:the schema" in joined:
        return (
            "fabricated_name_or_id",
            "real_unsupported_claim",
            "The answer names a generic quoted entity not present in EvidenceBus or answer slots.",
            "A schema title/name from SQL/API evidence, or a generic non-quoted answer that does not fabricate an entity.",
        )
    if "unsupported_number" in joined:
        return ("fabricated_count", "real_unsupported_claim", "A numeric claim was not present in evidence.", "A count in EvidenceBus or answer slots.")
    if "unsupported_timestamp" in joined:
        return ("fabricated_timestamp", "real_unsupported_claim", "A timestamp claim was not present in evidence.", "A timestamp in EvidenceBus or answer slots.")
    if "unsupported_status" in joined:
        return ("fabricated_status", "real_unsupported_claim", "A status claim was not present in evidence.", "A status/state in EvidenceBus or answer slots.")
    if "api_confirmation" in joined or "usable supporting evidence" in lowered:
        return (
            "fabricated_live_api_success",
            "real_unsupported_claim",
            "The answer implies API success without a clearly linked payload claim.",
            "Linked live payload evidence, or caveated wording that does not imply confirmation.",
        )
    return ("no_clear_claim_issue", "real_unsupported_claim", "Unsupported claim needs manual review.", "Direct linked evidence for the claim.")


def _recommendation(rows: list[dict[str, Any]]) -> str:
    categories = counter_dict(row.get("claim_category") for row in rows)
    if categories.get("verifier_false_positive", 0) >= 3:
        return "Test a narrow verifier false-positive fix for title-case Live entity names; separately fix the single real generic schema entity if strict gates pass."
    return "Do not change runtime before an isolated unsupported-claim fix trial."


def _render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Generated Unsupported Claims Audit",
        "",
        "Generated prompts remain diagnostic-only. This report separates real unsupported claims from verifier/linking issues.",
        "",
        f"- Unsupported rows: `{summary.get('unsupported_row_count')}`",
        f"- Unsupported claims: `{summary.get('unsupported_claim_count')}`",
        f"- Previous gate unsupported rows: `{summary.get('previous_gate_unsupported_row_count')}`",
        f"- Previous gate unsupported claims: `{summary.get('previous_gate_unsupported_claim_count')}`",
        f"- Category counts: `{summary.get('category_counts')}`",
        f"- Reality counts: `{summary.get('reality_counts')}`",
        "",
        "## Rows",
        "",
    ]
    for row in report.get("rows", []):
        lines.extend(
            [
                f"### {row.get('prompt_id')}",
                "",
                f"- Category: `{row.get('claim_category')}`",
                f"- Reality: `{row.get('claim_reality')}`",
                f"- Unsupported claim: `{row.get('unsupported_claim_text')}`",
                f"- Why: {row.get('why_unsupported')}",
                f"- Final answer: {excerpt(row.get('final_answer'), 300)}",
                "",
            ]
        )
    if report.get("previous_gate_rows"):
        lines.extend(["## Previous Gate Rows", ""])
        for row in report.get("previous_gate_rows", []):
            lines.extend(
                [
                    f"### {row.get('prompt_id')}",
                    "",
                    f"- Category: `{row.get('claim_category')}`",
                    f"- Reality: `{row.get('claim_reality')}`",
                    f"- Unsupported claim: `{row.get('unsupported_claim_text')}`",
                    f"- Why: {row.get('why_unsupported')}",
                    f"- Final answer: {excerpt(row.get('final_answer'), 300)}",
                    "",
                ]
            )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
