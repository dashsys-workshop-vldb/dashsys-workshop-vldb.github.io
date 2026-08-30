from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_ID_FILENAME = "gated_batch_run_id.txt"
DEFAULT_RUNTIME_NOISE_SECONDS = 0.005


def start_report_run(outputs_dir: Path) -> str:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{time.monotonic_ns()}"
    (outputs_dir / RUN_ID_FILENAME).write_text(run_id, encoding="utf-8")
    return run_id


def current_report_run_id(outputs_dir: Path) -> str:
    path = outputs_dir / RUN_ID_FILENAME
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    return start_report_run(outputs_dir)


def report_metadata(outputs_dir: Path, *, reset: bool = False) -> dict[str, Any]:
    run_id = start_report_run(outputs_dir) if reset else current_report_run_id(outputs_dir)
    return {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def report_is_fresh(path: Path, expected_run_id: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return payload.get("run_id") == expected_run_id


def runtime_budget_for_row(
    *,
    baseline_runtime: Any,
    trial_runtime: Any,
    acceptable_noise_seconds: float = DEFAULT_RUNTIME_NOISE_SECONDS,
) -> dict[str, Any]:
    baseline = float(baseline_runtime or 0.0)
    trial = float(trial_runtime or 0.0)
    delta = round(trial - baseline, 4)
    regression_pct = 0.0
    if baseline > 0 and delta > 0:
        regression_pct = round(delta / baseline, 4)
    over_twenty_pct = regression_pct > 0.20
    timing_noise_explanation = ""
    if over_twenty_pct and delta <= acceptable_noise_seconds:
        timing_noise_explanation = "absolute runtime delta is within acceptable timing-noise threshold"
    ok = delta <= acceptable_noise_seconds and (not over_twenty_pct or bool(timing_noise_explanation))
    return {
        "runtime_delta": delta,
        "runtime_regression_pct": regression_pct,
        "runtime_regression_over_20pct": over_twenty_pct,
        "timing_noise_explanation": timing_noise_explanation,
        "runtime_budget_ok": ok,
    }


def runtime_budget_summary(
    rows: list[dict[str, Any]],
    *,
    acceptable_noise_seconds: float = DEFAULT_RUNTIME_NOISE_SECONDS,
) -> dict[str, Any]:
    deltas = [float(row.get("runtime_delta") or 0.0) for row in rows]
    avg_delta = round(sum(deltas) / len(deltas), 4) if deltas else 0.0
    regressions = [
        row
        for row in rows
        if row.get("runtime_regression_over_20pct") and not row.get("timing_noise_explanation")
    ]
    return {
        "acceptable_noise_threshold_seconds": acceptable_noise_seconds,
        "avg_runtime_delta": avg_delta,
        "avg_runtime_budget_ok": avg_delta <= acceptable_noise_seconds,
        "row_runtime_regression_over_20pct_count": len(regressions),
        "runtime_budget_ok": avg_delta <= acceptable_noise_seconds and not regressions,
        "runtime_regression_query_ids": [row.get("query_id") for row in regressions],
    }
