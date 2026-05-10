#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.executor import AgentExecutor
from dashagent.llm_client import get_llm_client
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env


DEFAULT_LIMIT = 50


def main() -> int:
    args = parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    report = run_llm_semantic_router_shadow_eval(
        config,
        limit=args.limit,
        include_generated=not args.public_only,
        generated_suite_path=Path(args.generated_suite) if args.generated_suite else None,
    )
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "total_prompts": report.get("total_prompts"),
                "helper_called_prompts": report.get("helper_called_prompts"),
                "json": str(config.outputs_dir / "reports" / "llm_semantic_router_shadow_eval.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LLM semantic routing helper in shadow mode.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Prompt limit. Defaults to {DEFAULT_LIMIT}.")
    parser.add_argument("--public-only", action="store_true", help="Use only data/data.json prompts.")
    parser.add_argument("--generated-suite", help="Optional generated prompt suite path.")
    return parser.parse_args()


def run_llm_semantic_router_shadow_eval(
    config: Config | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    include_generated: bool = True,
    generated_suite_path: Path | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_root = config.outputs_dir / "llm_semantic_router_shadow_eval"
    output_root.mkdir(parents=True, exist_ok=True)

    client = get_llm_client()
    backend = _backend_metadata(client)
    prompts = _load_public_prompts(config)
    if include_generated:
        prompts.extend(_load_generated_prompts(generated_suite_path or (config.data_dir / "generated_prompt_suite.json")))
    selected = prompts[: max(0, min(limit, len(prompts)))]

    if not client.available():
        report = _build_skipped_report(config, selected, backend, client.generate_messages([]).get("reason", "LLM provider API key is not set"))
        _write_report(config, report)
        return report

    shadow_config = replace(
        config,
        enable_llm_semantic_router=True,
        llm_semantic_router_shadow_only=True,
    )
    executor = AgentExecutor(shadow_config)
    rows: list[dict[str, Any]] = []
    for item in selected:
        prompt_id = str(item.get("prompt_id") or item.get("query_id") or f"semantic_shadow_{len(rows) + 1:04d}")
        prompt = str(item.get("prompt") or item.get("query") or "")
        out_dir = output_root / prompt_id
        start = time.perf_counter()
        try:
            result = executor.run(prompt, strategy="SQL_FIRST_API_VERIFY", query_id=prompt_id, output_dir=out_dir)
            elapsed = time.perf_counter() - start
            trajectory = result.get("trajectory") or _load_json(out_dir / "trajectory.json")
            rows.append(_row_from_trajectory(item, trajectory, elapsed, out_dir))
        except Exception as exc:
            rows.append(
                redact_secrets(
                    {
                        "prompt_id": prompt_id,
                        "prompt": prompt,
                        "status": "failed",
                        "failure_category": "runtime_error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "runtime": round(time.perf_counter() - start, 4),
                        "output_dir": _rel(config, out_dir),
                    }
                )
            )

    report = _build_report(config, selected, rows, backend)
    _write_report(config, report)
    return report


def _load_public_prompts(config: Config) -> list[dict[str, Any]]:
    payload = _load_json(config.data_json_path)
    rows = payload if isinstance(payload, list) else payload.get("examples", []) if isinstance(payload, dict) else []
    prompts: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, dict):
            continue
        query = item.get("query") or item.get("question") or item.get("prompt") or item.get("input")
        if query:
            prompts.append({"prompt_id": item.get("id") or f"example_{index:03d}", "prompt": str(query), "source": "data/data.json"})
    return prompts


def _load_generated_prompts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = _load_json(path)
    if not isinstance(payload, list):
        return []
    prompts = []
    for item in payload:
        if isinstance(item, dict) and item.get("prompt"):
            prompts.append({"prompt_id": item.get("prompt_id"), "prompt": item.get("prompt"), "source": str(path), **item})
    return prompts


def _row_from_trajectory(item: dict[str, Any], trajectory: dict[str, Any], elapsed: float, out_dir: Path) -> dict[str, Any]:
    checkpoint = _semantic_checkpoint(trajectory)
    prompt = item.get("prompt") or item.get("query") or trajectory.get("original_query")
    return redact_secrets(
        {
            "prompt_id": item.get("prompt_id") or trajectory.get("query_id"),
            "prompt": prompt,
            "status": "passed",
            "source": item.get("source"),
            "eligible": bool(checkpoint.get("eligibility_reason")) or bool(checkpoint.get("helper_called")),
            "eligibility_reason": checkpoint.get("eligibility_reason", []),
            "helper_called": checkpoint.get("helper_called", False),
            "helper_valid": checkpoint.get("helper_valid", False),
            "helper_rejected_reason": checkpoint.get("helper_rejected_reason"),
            "deterministic_route_type": checkpoint.get("deterministic_route_type"),
            "helper_route_suggestion": checkpoint.get("helper_route_suggestion"),
            "would_change_route": checkpoint.get("would_change_route", False),
            "deterministic_domain_type": checkpoint.get("deterministic_domain_type"),
            "helper_likely_domain": checkpoint.get("helper_likely_domain"),
            "would_change_domain": checkpoint.get("would_change_domain", False),
            "helper_answer_intent": checkpoint.get("helper_answer_intent"),
            "would_change_intent": checkpoint.get("would_change_intent", False),
            "helper_confidence": checkpoint.get("helper_confidence"),
            "deterministic_confidence_before": checkpoint.get("deterministic_confidence_before"),
            "final_runtime_confidence": checkpoint.get("final_runtime_confidence"),
            "hint_applied": checkpoint.get("hint_applied", False),
            "hint_application_mode": checkpoint.get("hint_application_mode"),
            "applied_to_runtime": checkpoint.get("applied_to_runtime", False),
            "sdk_path_used": checkpoint.get("sdk_path_used"),
            "backend_type": checkpoint.get("backend_type"),
            "runtime": round(float(trajectory.get("runtime", elapsed) or elapsed), 4),
            "output_dir": str(out_dir),
        }
    )


def _build_skipped_report(config: Config, selected: list[dict[str, Any]], backend: dict[str, Any], reason: str) -> dict[str, Any]:
    return redact_secrets(
        {
            "report_type": "llm_semantic_router_shadow_eval",
            "diagnostic_only": True,
            "official_strict_score_computed": False,
            "status": "skipped",
            "skipped_reason": reason,
            "feature_flag_default": "off",
            "shadow_only": True,
            "total_prompts": len(selected),
            "helper_eligible_prompts": 0,
            "helper_called_prompts": 0,
            "valid_helper_outputs": 0,
            "rejected_helper_outputs": 0,
            "recommendation": "keep_disabled",
            "recommendation_reason": "No configured SDK backend/key was available for shadow evaluation.",
            **backend,
            "rows": [],
        }
    )


def _build_report(config: Config, selected: list[dict[str, Any]], rows: list[dict[str, Any]], backend: dict[str, Any]) -> dict[str, Any]:
    passed = [row for row in rows if row.get("status") == "passed"]
    called = [row for row in passed if row.get("helper_called")]
    valid = [row for row in called if row.get("helper_valid")]
    rejected = [row for row in called if not row.get("helper_valid")]
    disagreements = [row for row in valid if row.get("would_change_route") or row.get("would_change_domain") or row.get("would_change_intent")]
    recommendation = "keep_shadow_only" if valid else "keep_disabled"
    return redact_secrets(
        {
            "report_type": "llm_semantic_router_shadow_eval",
            "diagnostic_only": True,
            "official_strict_score_computed": False,
            "status": "complete",
            "feature_flag_default": "off",
            "shadow_only": True,
            "helper_scope": "routing_hints_only_no_final_answers",
            "total_prompts": len(selected),
            "passed_runtime_count": len(passed),
            "failed_runtime_count": len(rows) - len(passed),
            "helper_eligible_prompts": sum(1 for row in passed if row.get("eligible")),
            "helper_called_prompts": len(called),
            "valid_helper_outputs": len(valid),
            "rejected_helper_outputs": len(rejected),
            "route_disagreements": sum(1 for row in disagreements if row.get("would_change_route")),
            "domain_disagreements": sum(1 for row in disagreements if row.get("would_change_domain")),
            "intent_disagreements": sum(1 for row in disagreements if row.get("would_change_intent")),
            "rejection_reasons": dict(Counter(row.get("helper_rejected_reason") for row in rejected if row.get("helper_rejected_reason"))),
            "useful_synonym_examples": disagreements[:10],
            "wrong_suggestion_examples": rejected[:10],
            "recommendation": recommendation,
            "recommendation_reason": "Shadow-only diagnostic only; no strict-score promotion gate has run.",
            **backend,
            "rows": rows,
        }
    )


def _write_report(config: Config, report: dict[str, Any]) -> None:
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "llm_semantic_router_shadow_eval.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / "llm_semantic_router_shadow_eval.md").write_text(_render_markdown(report), encoding="utf-8")


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# LLM Semantic Routing Helper Shadow Eval",
        "",
        "Diagnostic only. This report does not compute official strict score and does not promote runtime behavior.",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Feature flag default: `{report.get('feature_flag_default')}`",
        f"- Shadow-only: `{report.get('shadow_only')}`",
        f"- Backend/model: `{report.get('model')}`",
        f"- Backend type: `{report.get('backend_type')}`",
        f"- SDK path used: `{report.get('sdk_path_used')}`",
        f"- Total prompts: `{report.get('total_prompts')}`",
        f"- Helper eligible prompts: `{report.get('helper_eligible_prompts')}`",
        f"- Helper called prompts: `{report.get('helper_called_prompts')}`",
        f"- Valid helper outputs: `{report.get('valid_helper_outputs')}`",
        f"- Rejected helper outputs: `{report.get('rejected_helper_outputs')}`",
        f"- Recommendation: `{report.get('recommendation')}`",
        "",
    ]
    if report.get("skipped_reason"):
        lines.append(f"Skipped reason: {report.get('skipped_reason')}")
        lines.append("")
    lines.extend(["## Rejection Reasons", ""])
    reasons = report.get("rejection_reasons") or {}
    if reasons:
        for key, value in sorted(reasons.items()):
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- `none`: `0`")
    lines.append("")
    return "\n".join(lines)


def _semantic_checkpoint(trajectory: dict[str, Any]) -> dict[str, Any]:
    for checkpoint in trajectory.get("checkpoints") or []:
        if isinstance(checkpoint, dict) and checkpoint.get("checkpoint_id") == "checkpoint_llm_semantic_routing_helper":
            output = checkpoint.get("output")
            return output if isinstance(output, dict) else {}
    return {}


def _backend_metadata(client: Any) -> dict[str, Any]:
    provider = client.provider_name()
    backend_type = "anthropic_sdk" if provider == "anthropic" else "openai_sdk" if provider in {"openai", "openrouter"} else "none"
    return {
        "provider": provider,
        "provider_type": "anthropic" if provider == "anthropic" else "openai_compatible",
        "backend_type": backend_type,
        "transport": backend_type,
        "sdk_path_used": backend_type in {"openai_sdk", "anthropic_sdk"},
        "model": client.model_name(),
        "llm_client_path_used": True,
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if path.suffix == ".json" else None


def _rel(config: Config, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
