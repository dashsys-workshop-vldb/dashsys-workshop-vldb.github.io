#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config


REQUIRED_QUERY_FILES = ["metadata.json", "filled_system_prompt.txt", "trajectory.json"]
SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(r"CLIENT_SECRET\s*=\s*[^\s]+", re.IGNORECASE),
    re.compile(r"ACCESS_TOKEN\s*=\s*[^\s]+", re.IGNORECASE),
    re.compile(r'"(?:access_token|client_secret|authorization)"\s*:\s*"(?!\[REDACTED\])[^"]{8,}"', re.IGNORECASE),
]


def main() -> int:
    config = Config.from_env(ROOT)
    report = check_submission_ready(config)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if report["ok"] else 1


def check_submission_ready(config: Config) -> dict[str, Any]:
    final_dir = config.outputs_dir / "final_submission"
    manifest_path = config.outputs_dir / "final_submission_manifest.json"
    checks: dict[str, Any] = {
        "source_code_zip_exists": (config.outputs_dir / "source_code.zip").exists(),
        "system_prompt_template_exists": (config.prompts_dir / "system_prompt_template.txt").exists(),
        "final_submission_manifest_exists": manifest_path.exists(),
        "failure_analysis_exists": (config.outputs_dir / "failure_analysis.json").exists() and (config.outputs_dir / "failure_analysis.md").exists(),
        "family_score_report_exists": (config.outputs_dir / "family_score_report.json").exists() and (config.outputs_dir / "family_score_report.md").exists(),
        "pareto_report_exists": (config.outputs_dir / "pareto_report.json").exists() and (config.outputs_dir / "pareto_report.md").exists(),
        "threshold_tuning_report_exists": (config.outputs_dir / "threshold_tuning_report.json").exists() and (config.outputs_dir / "threshold_tuning_report.md").exists(),
        "robustness_eval_exists": (config.outputs_dir / "robustness_eval.json").exists() and (config.outputs_dir / "robustness_eval.md").exists(),
        "final_submission_dir_exists": final_dir.exists(),
        "query_outputs": [],
        "json_parse_errors": [],
        "secret_scan": {"ok": True, "hits": []},
        "unresolved_api_path_placeholders": [],
        "unresolved_api_params_without_warning": [],
        "default_strategy_is_sql_first_api_verify": False,
    }

    manifest = {}
    if manifest_path.exists():
        manifest = load_json(manifest_path, checks, "manifest")
        checks["default_strategy_is_sql_first_api_verify"] = manifest.get("preferred_strategy") == "SQL_FIRST_API_VERIFY"

    if final_dir.exists():
        query_dirs = sorted(path for path in final_dir.iterdir() if path.is_dir() and path.name.startswith("query_"))
        for query_dir in query_dirs:
            query_check = {"query_id": query_dir.name, "files": {}, "trajectory_json_valid": False}
            for filename in REQUIRED_QUERY_FILES:
                path = query_dir / filename
                query_check["files"][filename] = path.exists()
                if filename.endswith(".json") and path.exists():
                    data = load_json(path, checks, str(path))
                    if filename == "trajectory.json" and data:
                        query_check["trajectory_json_valid"] = True
                        query_check["strategy"] = data.get("strategy")
                        query_check["required_trajectory_fields"] = required_trajectory_fields_present(data)
                        inspect_trajectory_for_readiness(data, checks, query_dir.name)
            checks["query_outputs"].append(query_check)
        checks["secret_scan"] = scan_for_secrets(final_dir)

    missing_query_files = [
        {"query_id": item["query_id"], "missing": [name for name, exists in item["files"].items() if not exists]}
        for item in checks["query_outputs"]
        if not all(item["files"].values())
    ]
    checks["missing_query_files"] = missing_query_files
    checks["query_output_count"] = len(checks["query_outputs"])
    checks["ok"] = all(
        [
            checks["source_code_zip_exists"],
            checks["system_prompt_template_exists"],
            checks["final_submission_manifest_exists"],
            checks["failure_analysis_exists"],
            checks["family_score_report_exists"],
            checks["pareto_report_exists"],
            checks["threshold_tuning_report_exists"],
            checks["robustness_eval_exists"],
            checks["final_submission_dir_exists"],
            checks["query_output_count"] > 0,
            not checks["json_parse_errors"],
            checks["secret_scan"]["ok"],
            not checks["unresolved_api_path_placeholders"],
            not checks["unresolved_api_params_without_warning"],
            checks["default_strategy_is_sql_first_api_verify"],
            not missing_query_files,
            all(item.get("required_trajectory_fields", False) for item in checks["query_outputs"]),
        ]
    )
    return checks


def load_json(path: Path, checks: dict[str, Any], label: str) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        checks["json_parse_errors"].append({"file": label, "error": str(exc)})
        return {}


def inspect_trajectory_for_readiness(trajectory: dict[str, Any], checks: dict[str, Any], query_id: str) -> None:
    plan_steps = []
    for step in trajectory.get("steps", []):
        if step.get("kind") == "plan":
            plan_steps.extend(step.get("steps", []))
        if step.get("kind") == "api_call":
            url = step.get("url", "")
            if "{" in str(url) or "}" in str(url):
                checks["unresolved_api_path_placeholders"].append({"query_id": query_id, "url": url})

    for step in plan_steps:
        if step.get("action") != "api":
            continue
        params = step.get("params", {})
        warnings = " ".join(step.get("warnings", []) or [])
        if contains_unresolved(params) and "unresolved_parameter" not in warnings:
            checks["unresolved_api_params_without_warning"].append(
                {"query_id": query_id, "url": step.get("url"), "params": params}
            )


def required_trajectory_fields_present(trajectory: dict[str, Any]) -> bool:
    required = ["final_answer", "tool_call_count", "runtime", "estimated_tokens"]
    return all(key in trajectory for key in required)


def contains_unresolved(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_unresolved(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_unresolved(item) for item in value)
    return isinstance(value, str) and bool(re.search(r"<[^>]+>", value))


def scan_for_secrets(root: Path) -> dict[str, Any]:
    hits = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".zip", ".png", ".jpg", ".jpeg", ".parquet"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append({"file": str(path), "pattern": pattern.pattern})
                break
    return {"ok": not hits, "hits": hits}


if __name__ == "__main__":
    raise SystemExit(main())
