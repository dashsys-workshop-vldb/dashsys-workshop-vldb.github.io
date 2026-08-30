#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import report_metadata
from scripts.run_endpoint_schema_rule_canary import _assert_allowed_output as _assert_canary_output
from scripts.run_endpoint_schema_rule_canary import run_endpoint_schema_rule_canary
from scripts.run_official_token_reduction_canary import protected_output_hash_snapshot
from scripts.run_official_token_reduction_eval import _avg, _load_json


OUTPUT_NAME = "endpoint_schema_rule_packaged_trial"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_endpoint_schema_rule_packaged_trial(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    _assert_allowed_output(config.outputs_dir, json_path)
    _assert_allowed_output(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    if not payload.get("protected_output_hashes_unchanged"):
        raise RuntimeError("Endpoint/schema packaged trial modified protected official outputs.")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def run_endpoint_schema_rule_packaged_trial(config: Config) -> dict[str, Any]:
    before_hashes = protected_output_hash_snapshot(config)
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_allowed_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    canary = _load_json(config.outputs_dir / "endpoint_schema_rule_canary.json") or run_endpoint_schema_rule_canary(config)
    if (canary.get("summary") or {}).get("recommendation") != "safe_for_packaged_accuracy_trial":
        after_hashes = protected_output_hash_snapshot(config)
        return _skipped_payload(
            config,
            before_hashes=before_hashes,
            after_hashes=after_hashes,
            reason="endpoint/schema canary did not recommend safe_for_packaged_accuracy_trial",
            canary=canary,
        )

    rows = []
    for row in canary.get("rows", []) or []:
        query_id = str(row.get("query_id") or "")
        trial_dir = output_root / query_id / "sql_first_api_verify"
        _assert_allowed_output(config.outputs_dir, trial_dir)
        trial_dir.mkdir(parents=True, exist_ok=True)
        source_dir = Path(str(row.get("canary_output_dir") or ""))
        for filename in ["metadata.json", "filled_system_prompt.txt", "trajectory.json"]:
            if (source_dir / filename).exists():
                shutil.copy2(source_dir / filename, trial_dir / filename)
        rows.append(
            {
                "query_id": query_id,
                "baseline_score": row.get("strict_score_before"),
                "trial_score": row.get("strict_score_after"),
                "score_delta": row.get("score_delta"),
                "baseline_correctness": row.get("correctness_before"),
                "trial_correctness": row.get("correctness_after"),
                "correctness_delta": row.get("correctness_delta"),
                "token_delta": row.get("token_delta"),
                "runtime_delta": row.get("runtime_delta"),
                "tool_delta": row.get("tool_delta"),
                "answer_changed": row.get("answer_changed"),
                "sql_changed": row.get("sql_changed"),
                "api_changed": row.get("api_changed"),
                "dry_run_labels_preserved": row.get("dry_run_labels_preserved"),
                "live_api_evidence_fabricated": row.get("live_api_evidence_fabricated"),
                "api_top_k_hit_delta": row.get("api_top_k_hit_delta"),
                "trial_output_dir": str(trial_dir),
            }
        )
    after_hashes = protected_output_hash_snapshot(config)
    protected_unchanged = before_hashes == after_hashes
    for row in rows:
        row["protected_hashes_unchanged"] = protected_unchanged
        safe, reason = _row_safe(row)
        row["safe_to_promote"] = safe
        row["rejection_reason"] = reason
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "packaged_execution_changed": False,
        "feature_flag_default": config.enable_endpoint_schema_rule_candidates,
        "feature_flag_enabled_for_trial": True,
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "compact_context_enabled": config.enable_compact_context_when_schema_vote_safe,
        "protected_output_hashes_before": before_hashes,
        "protected_output_hashes_after": after_hashes,
        "protected_output_hashes_unchanged": protected_unchanged,
        "rows": rows,
        "summary": _summary(rows, protected_unchanged=protected_unchanged),
        "notes": ["Endpoint/schema packaged trial is isolated and does not overwrite official outputs."],
    }


def _skipped_payload(
    config: Config,
    *,
    before_hashes: dict[str, Any],
    after_hashes: dict[str, Any],
    reason: str,
    canary: dict[str, Any],
) -> dict[str, Any]:
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "skipped": True,
        "skip_reason": reason,
        "packaged_execution_changed": False,
        "feature_flag_default": config.enable_endpoint_schema_rule_candidates,
        "feature_flag_enabled_for_trial": False,
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "compact_context_enabled": config.enable_compact_context_when_schema_vote_safe,
        "protected_output_hashes_before": before_hashes,
        "protected_output_hashes_after": after_hashes,
        "protected_output_hashes_unchanged": before_hashes == after_hashes,
        "rows": [],
        "summary": {
            "total_rows": 0,
            "safe_rows": 0,
            "unsafe_rows": 0,
            "avg_score_delta": 0.0,
            "avg_correctness_delta": 0.0,
            "avg_token_delta": 0.0,
            "avg_runtime_delta": 0.0,
            "avg_tool_delta": 0.0,
            "api_top_k_hit_rate_delta": (canary.get("summary") or {}).get("api_top_k_hit_rate_delta", 0.0),
            "recommendation": "keep_shadow_only",
            "skipped": True,
            "skip_reason": reason,
        },
        "notes": ["Packaged trial was skipped because the canary did not pass its measurable-improvement gate."],
    }


def _row_safe(row: dict[str, Any]) -> tuple[bool, str]:
    failures = []
    if float(row.get("score_delta") or 0.0) < 0:
        failures.append("strict_score_regression")
    if float(row.get("correctness_delta") or 0.0) < 0:
        failures.append("correctness_regression")
    if int(row.get("token_delta") or 0) > 0:
        failures.append("token_regression")
    if float(row.get("runtime_delta") or 0.0) > 0:
        failures.append("runtime_regression")
    if int(row.get("tool_delta") or 0) > 0:
        failures.append("tool_regression")
    for key, failure in [
        ("answer_changed", "answer_changed"),
        ("sql_changed", "sql_changed"),
        ("api_changed", "api_changed"),
        ("live_api_evidence_fabricated", "live_api_evidence_fabricated"),
    ]:
        if row.get(key):
            failures.append(failure)
    if row.get("dry_run_labels_preserved") is not True:
        failures.append("dry_run_labels_changed")
    if row.get("protected_hashes_unchanged") is False:
        failures.append("protected_output_hash_changed")
    return not failures, "; ".join(failures)


def _summary(rows: list[dict[str, Any]], *, protected_unchanged: bool) -> dict[str, Any]:
    avg_score = _avg(row.get("score_delta") for row in rows)
    avg_correctness = _avg(row.get("correctness_delta") for row in rows)
    avg_token = _avg(row.get("token_delta") for row in rows)
    avg_runtime = _avg(row.get("runtime_delta") for row in rows)
    avg_tool = _avg(row.get("tool_delta") for row in rows)
    topk_delta = _avg(row.get("api_top_k_hit_delta") for row in rows)
    improved = avg_score > 0 or avg_correctness > 0 or topk_delta > 0
    all_safe = bool(rows) and all(row.get("safe_to_promote") for row in rows) and protected_unchanged
    recommendation = "safe_to_promote_endpoint_schema_rules" if all_safe and improved else "keep_shadow_only"
    if rows and not all_safe:
        recommendation = "unsafe_do_not_enable"
    return {
        "total_rows": len(rows),
        "safe_rows": sum(1 for row in rows if row.get("safe_to_promote")),
        "unsafe_rows": sum(1 for row in rows if not row.get("safe_to_promote")),
        "avg_score_delta": avg_score,
        "avg_correctness_delta": avg_correctness,
        "avg_token_delta": avg_token,
        "avg_runtime_delta": avg_runtime,
        "avg_tool_delta": avg_tool,
        "api_top_k_hit_rate_delta": topk_delta,
        "protected_output_hashes_unchanged": protected_unchanged,
        "recommendation": recommendation,
    }


def _assert_allowed_output(outputs_dir: Path, path: Path) -> None:
    allowed_files = {(outputs_dir / f"{OUTPUT_NAME}.json").resolve(), (outputs_dir / f"{OUTPUT_NAME}.md").resolve()}
    resolved = path.resolve()
    if resolved in allowed_files:
        return
    try:
        resolved.relative_to((outputs_dir / OUTPUT_NAME).resolve())
        return
    except ValueError as exc:
        raise RuntimeError(f"Refusing to write endpoint/schema trial artifact outside isolated paths: {path}") from exc


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Endpoint/Schema Rule Packaged Trial",
        "",
        f"- Skipped: {payload.get('skipped', False)}",
        f"- Recommendation: `{summary.get('recommendation')}`",
        f"- Rows: {summary.get('total_rows')}",
        f"- Avg score/correctness delta: {summary.get('avg_score_delta')} / {summary.get('avg_correctness_delta')}",
        f"- API top-k hit-rate delta: {summary.get('api_top_k_hit_rate_delta')}",
        "",
    ]
    if payload.get("skip_reason"):
        lines.append(f"- Skip reason: {payload['skip_reason']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
