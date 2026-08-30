#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.api_client import AdobeAPIClient, AdobeCredentials
from dashagent.config import Config
from dashagent.executor import AgentExecutor
from dashagent.trajectory import redact_secrets
from dashagent.adobe_env import DEFAULT_ADOBE_BASE_URL
from scripts.run_full_generated_prompt_suite_diagnostic import _row_from_result


OUTPUT_ROOT_NAME = "generated_prompt_suite_local_diagnostic"
REPORT_STEM = "generated_prompt_suite_local_diagnostic"


def main() -> int:
    args = parse_args()
    config = Config.from_env(ROOT)
    report = run_generated_prompt_suite_local_diagnostic(
        config,
        suite_path=Path(args.suite) if args.suite else config.data_dir / "generated_prompt_suite.json",
        limit=args.limit,
        clean=args.clean,
    )
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "total_prompts": report.get("total_prompts"),
                "executed_prompts": report.get("executed_prompts"),
                "dry_run_only": report.get("dry_run_only"),
                "report": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all generated prompts in local dry-run diagnostic mode.")
    parser.add_argument("--suite", help="Path to generated_prompt_suite.json. Defaults to data/generated_prompt_suite.json.")
    parser.add_argument("--limit", type=int, default=None, help="Optional debug limit. Default runs the full suite.")
    parser.add_argument("--clean", action="store_true", help=f"Remove only outputs/{OUTPUT_ROOT_NAME} before running.")
    return parser.parse_args()


def run_generated_prompt_suite_local_diagnostic(
    config: Config | None = None,
    *,
    suite_path: Path | None = None,
    limit: int | None = None,
    clean: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    suite_path = suite_path or config.data_dir / "generated_prompt_suite.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    if not isinstance(suite, list):
        raise ValueError(f"Generated prompt suite must be a JSON list: {suite_path}")

    output_root = config.outputs_dir / OUTPUT_ROOT_NAME
    if clean:
        _clean_output(config, output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    selected = suite[: len(suite) if limit is None else max(0, min(limit, len(suite)))]
    executor = AgentExecutor(config, api_client=_dry_run_api_client(config))
    rows: list[dict[str, Any]] = []
    for item in selected:
        prompt_id = str(item.get("prompt_id") or f"local_gen_{len(rows) + 1:04d}")
        prompt = str(item.get("prompt") or "")
        out_dir = output_root / prompt_id
        start = time.perf_counter()
        try:
            result = executor.run(prompt, strategy="SQL_FIRST_API_VERIFY", query_id=prompt_id, output_dir=out_dir)
            elapsed = time.perf_counter() - start
            trajectory = result.get("trajectory") or _load_json(out_dir / "trajectory.json")
            row = _local_row(config, item, result, trajectory, elapsed, out_dir)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            row = {
                "prompt_id": prompt_id,
                "prompt": prompt,
                "status": "failed",
                "diagnostic_only": True,
                "official_score_claim": False,
                "promotion_allowed": False,
                "generated_prompt_score_claim": False,
                "failure_category": "runtime_error",
                "error": f"{type(exc).__name__}: {exc}",
                "runtime": round(elapsed, 4),
                "generation_type": item.get("generation_type"),
                "domain_family": item.get("domain_family", "unknown"),
                "answer_intent": item.get("expected_answer_intent_diagnostic", "UNKNOWN"),
                "output_dir": _rel(config, out_dir),
            }
        rows.append(redact_secrets(row))

    report = redact_secrets(_build_report(config, suite, selected, rows, suite_path))
    (reports_dir / f"{REPORT_STEM}.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _dry_run_api_client(config: Config) -> AdobeAPIClient:
    credentials = AdobeCredentials(
        client_id=None,
        client_secret=None,
        api_key=None,
        ims_org=None,
        sandbox=None,
        access_token=None,
        base_url=DEFAULT_ADOBE_BASE_URL,
    )
    return AdobeAPIClient(config, credentials=credentials)


def _local_row(
    config: Config,
    item: dict[str, Any],
    result: dict[str, Any],
    trajectory: dict[str, Any],
    elapsed: float,
    out_dir: Path,
) -> dict[str, Any]:
    row = _row_from_result(config, item, result, trajectory, elapsed, out_dir)
    final_answer = str(row.get("final_answer") or "")
    prompt = str(item.get("prompt") or "")
    row.update(
        {
            "diagnostic_only": True,
            "official_score_claim": False,
            "official_strict_score_computed": False,
            "promotion_allowed": False,
            "generated_prompt_score_claim": False,
            "local_dry_run_safe_mode": True,
            "live_api_calls": 0,
            "dry_run_api_calls": int(row.get("dry_run_count") or 0),
            "answer_too_vague_advisory": _answer_too_vague(final_answer),
            "missing_count_or_name_advisory": _missing_count_or_name(prompt, final_answer),
            "heuristics_are_advisory_only": True,
            "output_dir": _rel(config, out_dir),
        }
    )
    return row


def _build_report(
    config: Config,
    suite: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    suite_path: Path,
) -> dict[str, Any]:
    passed = [row for row in rows if row.get("status") == "passed"]
    failed = [row for row in rows if row.get("status") != "passed"]
    validation_fails = [row for row in rows if int(row.get("validation_failures") or 0) > 0]
    zero_row = [row for row in passed if row.get("zero_row_sql")]
    vague = [row for row in passed if row.get("answer_too_vague_advisory")]
    missing = [row for row in passed if row.get("missing_count_or_name_advisory")]
    route_mismatches = [row for row in passed if row.get("route_matches_diagnostic") is False]
    domain_mismatches = [row for row in passed if row.get("domain_matches_diagnostic") is False]
    candidate_groups = _candidate_groups(rows)
    return {
        "report_type": REPORT_STEM,
        "status": "complete",
        "diagnostic_only": True,
        "official_score_claim": False,
        "official_strict_score_computed": False,
        "promotion_allowed": False,
        "generated_prompt_score_claim": False,
        "heuristics_are_advisory_only": True,
        "dry_run_only": True,
        "live_api_required": False,
        "live_api_calls": 0,
        "strategy": "SQL_FIRST_API_VERIFY",
        "suite_path": _rel(config, suite_path),
        "output_root": f"outputs/{OUTPUT_ROOT_NAME}",
        "total_prompts": len(suite),
        "executed_prompts": len(selected),
        "runtime_pass_count": len(passed),
        "runtime_fail_count": len(failed),
        "validation_fail_count": len(validation_fails),
        "route_distribution": dict(Counter(row.get("actual_route", "UNKNOWN") for row in passed)),
        "domain_distribution": dict(Counter(row.get("domain_type", "UNKNOWN") for row in passed)),
        "answer_intent_distribution": dict(Counter(row.get("actual_answer_intent", "UNKNOWN") for row in passed)),
        "dry_run_api_call_count": sum(int(row.get("dry_run_api_calls") or 0) for row in passed),
        "zero_row_sql_count": len(zero_row),
        "answer_too_vague_advisory_count": len(vague),
        "missing_count_or_name_advisory_count": len(missing),
        "route_domain_gaps": {
            "route_mismatch_count": len(route_mismatches),
            "domain_mismatch_count": len(domain_mismatches),
            "examples": route_mismatches[:10] + domain_mismatches[:10],
        },
        "sql_template_gaps": {"count": len(zero_row), "examples": zero_row[:10]},
        "answer_template_gaps": {"count": len(vague) + len(missing), "examples": (vague + missing)[:10]},
        "top_failure_categories": dict(Counter(row.get("failure_category", "ok") for row in rows)),
        "safest_targeted_improvement_candidates": candidate_groups,
        "deterministic_improvement_gate": {
            "minimum_repeated_gap_count": 3,
            "requires_schema_or_evidence_support": True,
            "requires_focused_tests": True,
            "requires_strict_eval_no_regression": True,
            "requires_hidden_style_no_regression": True,
            "automatic_runtime_fix_applied": False,
            "reason": "diagnostic report only; runtime fixes require separate evidence-backed implementation and no-regression validation",
        },
        "runtime_improvement_applied": False,
        "no_safe_deterministic_improvement_applied": True,
        "rows": rows,
    }


def _candidate_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counters: dict[str, Counter[str]] = {
        "route_mismatch": Counter(),
        "domain_mismatch": Counter(),
        "zero_row_sql": Counter(),
        "answer_template": Counter(),
    }
    for row in rows:
        domain = str(row.get("domain_family") or row.get("domain_type") or "unknown")
        intent = str(row.get("answer_intent") or row.get("actual_answer_intent") or "UNKNOWN")
        if row.get("route_matches_diagnostic") is False:
            counters["route_mismatch"][domain] += 1
        if row.get("domain_matches_diagnostic") is False:
            counters["domain_mismatch"][domain] += 1
        if row.get("zero_row_sql"):
            counters["zero_row_sql"][domain] += 1
        if row.get("answer_too_vague_advisory") or row.get("missing_count_or_name_advisory"):
            counters["answer_template"][f"{domain}:{intent}"] += 1
    out = []
    for category, counter in counters.items():
        for group, count in counter.most_common():
            if count >= 3:
                out.append(
                    {
                        "category": category,
                        "group": group,
                        "count": count,
                        "advisory_only": True,
                        "safe_to_apply_automatically": False,
                    }
                )
    return out[:20]


def _answer_too_vague(answer: str) -> bool:
    text = answer.strip().lower()
    if not text:
        return True
    vague_phrases = ("it depends", "cannot determine", "not enough information", "unable to determine")
    return len(text.split()) < 4 or any(phrase in text for phrase in vague_phrases)


def _missing_count_or_name(prompt: str, answer: str) -> bool:
    prompt_l = prompt.lower()
    answer_l = answer.lower()
    asks_count = any(token in prompt_l for token in ("how many", "count", "number of", "total"))
    asks_list = any(token in prompt_l for token in ("list", "which", "what are", "names"))
    if asks_count and not any(ch.isdigit() for ch in answer_l):
        return True
    if asks_list and any(phrase in answer_l for phrase in ("unavailable", "could not", "no matching")):
        return True
    return False


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Generated Prompt Suite Local Diagnostic",
        "",
        "Diagnostic coverage only. This local run forces Adobe API calls into dry-run mode and is not official strict-score evidence.",
        "",
        f"- Total prompts: `{report.get('total_prompts')}`",
        f"- Executed prompts: `{report.get('executed_prompts')}`",
        f"- Runtime pass count: `{report.get('runtime_pass_count')}`",
        f"- Runtime fail count: `{report.get('runtime_fail_count')}`",
        f"- Validation fail count: `{report.get('validation_fail_count')}`",
        f"- Dry-run API call count: `{report.get('dry_run_api_call_count')}`",
        f"- Zero-row SQL count: `{report.get('zero_row_sql_count')}`",
        f"- Vague-answer advisory count: `{report.get('answer_too_vague_advisory_count')}`",
        f"- Missing count/name advisory count: `{report.get('missing_count_or_name_advisory_count')}`",
        f"- Official score claim: `{report.get('official_score_claim')}`",
        f"- Promotion allowed: `{report.get('promotion_allowed')}`",
        f"- No safe deterministic improvement applied: `{report.get('no_safe_deterministic_improvement_applied')}`",
        "",
        "## Top Failure Categories",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted((report.get("top_failure_categories") or {}).items()))
    lines.extend(["", "## Candidate Groups Requiring Review", ""])
    candidates = report.get("safest_targeted_improvement_candidates") or []
    if candidates:
        for item in candidates:
            lines.append(f"- `{item.get('category')}` / `{item.get('group')}`: `{item.get('count')}` advisory cases")
    else:
        lines.append("- No repeated diagnostic-only candidate group reached the review threshold.")
    lines.extend(
        [
            "",
            "Heuristics in this report are advisory only and cannot support promotion or official score claims.",
            "",
        ]
    )
    return "\n".join(lines)


def _clean_output(config: Config, output_root: Path) -> None:
    expected = (config.outputs_dir / OUTPUT_ROOT_NAME).resolve()
    if output_root.resolve() != expected:
        raise ValueError(f"Refusing to clean unexpected path: {output_root}")
    if output_root.exists():
        shutil.rmtree(output_root)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _rel(config: Config, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root.resolve()).as_posix()
    except Exception:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
