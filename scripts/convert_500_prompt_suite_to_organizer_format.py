#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.endpoint_catalog import EndpointCatalog


DEFAULT_SUITE = ROOT / "data" / "benchmarks" / "dashagent_500_prompt_suite.jsonl"
DEFAULT_GOLD = ROOT / "data" / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "benchmarks" / "dashagent_500_organizer_style.json"
DEFAULT_MANIFEST = ROOT / "data" / "benchmarks" / "dashagent_500_organizer_style_manifest.json"
DEFAULT_REPORT_JSON = ROOT / "outputs" / "reports" / "dashagent_500_organizer_style_conversion.json"
DEFAULT_REPORT_MD = ROOT / "outputs" / "reports" / "dashagent_500_organizer_style_conversion.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert the internal 500-prompt benchmark into organizer-style eval JSON.")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    args = parser.parse_args()

    payload = convert_suite(args.suite, args.gold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"examples": payload["examples"]}, indent=2, sort_keys=True), encoding="utf-8")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(payload["manifest"], indent=2, sort_keys=True), encoding="utf-8")
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(payload["report"], indent=2, sort_keys=True), encoding="utf-8")
    args.report_md.write_text(render_report(payload["report"], args.output, args.manifest), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "manifest": str(args.manifest), "examples": len(payload["examples"])}, indent=2))
    return 0


def convert_suite(suite_path: Path, gold_path: Path) -> dict[str, Any]:
    runtime_rows = [_loads_jsonl(line, suite_path, index) for index, line in enumerate(suite_path.read_text(encoding="utf-8").splitlines(), 1)]
    gold_rows = [_loads_jsonl(line, gold_path, index) for index, line in enumerate(gold_path.read_text(encoding="utf-8").splitlines(), 1)]
    gold_by_id = {str(row["prompt_id"]): row for row in gold_rows}
    catalog = EndpointCatalog(Config.from_env(ROOT))
    examples: list[dict[str, Any]] = []
    lost_fields = Counter()
    endpoint_failures: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    evidence_counts: Counter[str] = Counter()

    for row in runtime_rows:
        prompt_id = str(row["prompt_id"])
        gold = gold_by_id.get(prompt_id)
        if gold is None:
            raise ValueError(f"Missing gold row for {prompt_id}")
        category_counts[str(row.get("category") or "unknown")] += 1
        evidence_counts[str(gold.get("expected_evidence_need") or "unknown")] += 1
        gold_api, api_loss = _convert_gold_api(gold, catalog)
        lost_fields.update(api_loss)
        expected_trace = gold.get("expected_observable_trace") or []
        if expected_trace:
            lost_fields["expected_observable_trace_sidecar_only"] += 1
        for key in ("acceptable_answer_variants", "required_facts", "forbidden_claims", "grading_rubric", "expected_tool_calls"):
            if gold.get(key):
                lost_fields[f"{key}_sidecar_only"] += 1
        example = {
            "id": prompt_id,
            "query": str(row.get("prompt") or ""),
            "answer": gold.get("gold_answer"),
        }
        oracle_sql = (gold.get("oracle_evidence") or {}).get("oracle_sql")
        if oracle_sql:
            example["gold_sql"] = oracle_sql
        if gold_api:
            example["gold_api"] = gold_api
        if gold.get("gold_answer_type"):
            example["gold_answer_type"] = gold.get("gold_answer_type")
        examples.append(example)
        if gold.get("expected_tool_calls", {}).get("api_required") and not gold_api:
            endpoint_failures.append(
                {
                    "prompt_id": prompt_id,
                    "expected_api_families": gold.get("expected_tool_calls", {}).get("expected_api_families", []),
                    "oracle_api_endpoint": (gold.get("oracle_evidence") or {}).get("oracle_api_endpoint"),
                }
            )

    manifest = {
        "source_suite": str(suite_path),
        "source_gold": str(gold_path),
        "converted_count": len(examples),
        "runtime_fields_in_converted_examples": sorted({key for example in examples for key in example}),
        "agent_visible_fields": ["id", "query"],
        "gold_fields_used_by_evaluator": ["gold_sql", "gold_api", "answer"],
        "category_distribution": dict(sorted(category_counts.items())),
        "evidence_need_distribution": dict(sorted(evidence_counts.items())),
        "endpoint_mapping_failures": endpoint_failures,
        "lost_or_sidecar_fields": dict(sorted(lost_fields.items())),
        "organizer_equivalent": False,
        "organizer_equivalence_note": "This is an organizer-style strict eval input built from internal heuristic gold; richer internal rubrics remain sidecar-only.",
    }
    report = {
        "report_type": "dashagent_500_organizer_style_conversion",
        "converted_count": len(examples),
        "category_distribution": manifest["category_distribution"],
        "evidence_need_distribution": manifest["evidence_need_distribution"],
        "runtime_query_object_contains_category_tags": False,
        "gold_hidden_from_runtime": True,
        "oracle_sql_hidden_from_runtime": True,
        "expected_trace_hidden_from_runtime": True,
        "endpoint_mapping_failure_count": len(endpoint_failures),
        "lost_or_sidecar_fields": manifest["lost_or_sidecar_fields"],
        "organizer_equivalent": False,
        "notes": [
            "Converted rows expose only id/query to the agent runtime through EvalHarness.",
            "Gold SQL/API/answer fields are used only by the strict evaluator after execution.",
            "Expected observable traces and detailed rubric fields are retained in the original benchmark gold, not embedded as runtime inputs.",
        ],
    }
    return {"examples": examples, "manifest": manifest, "report": report}


def _loads_jsonl(line: str, path: Path, line_number: int) -> dict[str, Any]:
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}:{line_number}: expected object row")
    return value


def _convert_gold_api(gold: dict[str, Any], catalog: EndpointCatalog) -> tuple[list[dict[str, Any]] | None, Counter[str]]:
    losses: Counter[str] = Counter()
    oracle = gold.get("oracle_evidence") if isinstance(gold.get("oracle_evidence"), dict) else {}
    endpoint_value = oracle.get("oracle_api_endpoint")
    if not endpoint_value:
        return None, losses
    if isinstance(endpoint_value, dict):
        method = str(endpoint_value.get("method") or endpoint_value.get("http_method") or "GET").upper()
        path = endpoint_value.get("path") or endpoint_value.get("url") or endpoint_value.get("endpoint")
        if path:
            return [{"method": method, "path": str(path), "params": dict(endpoint_value.get("params", {}) or {})}], losses
        losses["api_endpoint_dict_missing_path"] += 1
        return None, losses

    endpoint_id = str(endpoint_value)
    endpoint = catalog.by_id(endpoint_id)
    if endpoint is None:
        losses["api_endpoint_id_not_in_catalog"] += 1
        return None, losses
    if endpoint.method != "GET" or endpoint.path_params:
        losses["api_endpoint_not_safe_static_get"] += 1
        return None, losses
    return [{"method": endpoint.method, "path": endpoint.path, "params": dict(endpoint.common_params or {})}], losses


def render_report(report: dict[str, Any], output_path: Path, manifest_path: Path) -> str:
    lines = [
        "# DashAgent 500 Organizer-Style Conversion",
        "",
        f"- Converted examples: `{report['converted_count']}`",
        f"- Output dataset: `{output_path}`",
        f"- Manifest: `{manifest_path}`",
        f"- Organizer-equivalent: `{report['organizer_equivalent']}`",
        f"- Endpoint mapping failures: `{report['endpoint_mapping_failure_count']}`",
        f"- Runtime category/tags exposed: `{report['runtime_query_object_contains_category_tags']}`",
        f"- Gold hidden from runtime: `{report['gold_hidden_from_runtime']}`",
        "",
        "## Category Distribution",
        "",
    ]
    for key, value in report["category_distribution"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Evidence Need Distribution", ""])
    for key, value in report["evidence_need_distribution"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Sidecar / Lost Strict Fields", ""])
    for key, value in report["lost_or_sidecar_fields"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Notes", ""])
    for note in report["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
