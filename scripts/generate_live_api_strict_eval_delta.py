#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


BASELINE_NAME = "pre_live_api_eval_results_strict.json"
META_NAME = "pre_live_api_eval_results_strict.meta.json"
REPORT_STEM = "live_api_strict_eval_delta"
STRATEGY = "SQL_FIRST_API_VERIFY"


def main() -> int:
    parser = argparse.ArgumentParser(description="Preserve pre-live strict baseline and generate live API strict eval delta.")
    parser.add_argument("--reason", default="pre_live_api_strict_eval_baseline")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    payload = generate_live_api_strict_eval_delta(config, reason=args.reason)
    print(json.dumps({"report": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "baseline_preserved": payload.get("baseline_preserved")}, indent=2, sort_keys=True))
    return 0


def generate_live_api_strict_eval_delta(config: Config | None = None, *, reason: str = "pre_live_api_strict_eval_baseline") -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    baselines_dir = reports_dir / "baselines"
    reports_dir.mkdir(parents=True, exist_ok=True)
    baselines_dir.mkdir(parents=True, exist_ok=True)

    baseline_info = preserve_pre_live_baseline(config, reason=reason)
    current_path = config.outputs_dir / "eval_results_strict.json"
    baseline_path = baselines_dir / BASELINE_NAME
    baseline = _load_json(baseline_path)
    current = _load_json(current_path)
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "infrastructure_validation_only": True,
            "official_score_claim": False,
            "automatic_promotion": False,
            "baseline_preserved": baseline_info,
            "strategy": STRATEGY,
            "summary_delta": _summary_delta(baseline, current),
            "rows_helped": _row_examples(baseline, current, predicate=lambda delta: delta > 0),
            "rows_hurt": _row_examples(baseline, current, predicate=lambda delta: delta < 0),
            "rows_unchanged": _row_examples(baseline, current, predicate=lambda delta: delta == 0),
            "rows_switched_from_dry_run_to_live_api": "unavailable_without_baseline_trajectory_snapshot",
            "live_api_evidence_changed_answer": "requires trajectory-level before/after snapshot",
            "sql_api_conflicts": "requires trajectory-level before/after snapshot",
            "api_errors_hurt": "requires trajectory-level before/after snapshot",
            "recommendation": "diagnostic_only_no_promotion",
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def preserve_pre_live_baseline(config: Config, *, reason: str) -> dict[str, Any]:
    source = config.outputs_dir / "eval_results_strict.json"
    baselines_dir = config.outputs_dir / "reports" / "baselines"
    target = baselines_dir / BASELINE_NAME
    meta = baselines_dir / META_NAME
    if not source.exists():
        return {"created": False, "reason": "source_missing", "source_path": str(source)}
    source_sha = _sha256(source)
    if target.exists() and meta.exists():
        return {"created": False, "reason": "baseline_already_exists", "source_path": str(source), "target_path": str(target), "source_sha256": source_sha}
    baselines_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source),
        "source_sha256": source_sha,
        "reason": reason,
    }
    meta.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return {"created": True, "target_path": str(target), **metadata}


def _summary_delta(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    base = ((baseline.get("summary") or {}).get("by_strategy") or {}).get(STRATEGY, {})
    cur = ((current.get("summary") or {}).get("by_strategy") or {}).get(STRATEGY, {})
    keys = {
        "final_score": "avg_final_score",
        "sql_score": "avg_sql_score",
        "api_score": "avg_api_score",
        "answer_score": "avg_answer_score",
        "tool_count": "avg_tool_call_count",
        "tokens": "avg_estimated_tokens",
        "runtime": "avg_runtime",
    }
    return {
        name: {
            "previous": base.get(source_key),
            "current": cur.get(source_key),
            "delta": _delta(cur.get(source_key), base.get(source_key)),
        }
        for name, source_key in keys.items()
    }


def _row_examples(baseline: dict[str, Any], current: dict[str, Any], *, predicate: Any) -> list[dict[str, Any]]:
    base_rows = {
        (row.get("query_id"), row.get("strategy")): row
        for row in baseline.get("rows", [])
        if isinstance(row, dict) and row.get("strategy") == STRATEGY
    }
    examples = []
    for row in current.get("rows", []):
        if not isinstance(row, dict) or row.get("strategy") != STRATEGY:
            continue
        old = base_rows.get((row.get("query_id"), row.get("strategy")))
        if not old:
            continue
        delta = _delta(row.get("final_score"), old.get("final_score"))
        if isinstance(delta, (int, float)) and predicate(delta):
            examples.append(
                {
                    "query_id": row.get("query_id"),
                    "final_score_before": old.get("final_score"),
                    "final_score_after": row.get("final_score"),
                    "final_score_delta": delta,
                    "answer_score_delta": _delta(row.get("answer_score"), old.get("answer_score")),
                    "sql_score_delta": _delta(row.get("sql_score"), old.get("sql_score")),
                    "api_score_delta": _delta(row.get("api_score"), old.get("api_score")),
                }
            )
    return examples[:20]


def _delta(current: Any, previous: Any) -> float | None:
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    return round(float(current) - float(previous), 4)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Live API Strict Eval Delta",
        "",
        "Diagnostic comparison only. This report does not promote any strategy.",
        "",
        f"- Baseline: `{payload.get('baseline_preserved', {}).get('target_path')}`",
        f"- Recommendation: `{payload.get('recommendation')}`",
        "",
        "## Summary Delta",
        "",
    ]
    for key, value in (payload.get("summary_delta") or {}).items():
        lines.append(f"- `{key}` previous=`{value.get('previous')}` current=`{value.get('current')}` delta=`{value.get('delta')}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())

