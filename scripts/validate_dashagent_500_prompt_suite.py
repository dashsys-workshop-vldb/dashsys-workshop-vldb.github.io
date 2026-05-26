#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashagent.config import DEFAULT_CONFIG
from dashagent.db import DuckDBDatabase, is_read_only_sql
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.prompt_semantic_ir import normalize_prompt_text
from scripts.generate_dashagent_500_prompt_suite import CATEGORY_TARGETS, RUNTIME_GOLD_FORBIDDEN


PRIVATE_REASONING_PATTERNS = re.compile(
    r"\b(chain[- ]of[- ]thought|private reasoning|hidden reasoning|scratchpad|let me think step by step)\b",
    re.IGNORECASE,
)
SECRET_PATTERNS = re.compile(
    r"sk-[A-Za-z0-9_-]{12,}|"
    r"OPENAI_API_KEY\s*=|ANTHROPIC_API_KEY\s*=|"
    r"Authorization:\s*Bearer|"
    r"ADOBE_ACCESS_TOKEN\s*=|ADOBE_API_KEY\s*=|ADOBE_CLIENT_SECRET\s*=|CLIENT_SECRET\s*=",
    re.IGNORECASE,
)

REQUIRED_RUNTIME_FIELDS = {"prompt_id", "prompt", "category", "difficulty", "domain_family", "split", "tags"}
REQUIRED_GOLD_FIELDS = {
    "prompt_id",
    "gold_answer",
    "gold_answer_type",
    "acceptable_answer_variants",
    "required_facts",
    "forbidden_claims",
    "expected_route",
    "expected_evidence_need",
    "expected_tool_calls",
    "expected_observable_trace",
    "oracle_evidence",
    "grading_rubric",
}


def validate_suite(
    *,
    suite: Path | str | None = None,
    gold: Path | str | None = None,
    manifest: Path | str | None = None,
    suite_path: Path | str | None = None,
    gold_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    report_dir: Path | str | None = None,
) -> dict[str, Any]:
    suite_input = suite_path if suite_path is not None else suite
    gold_input = gold_path if gold_path is not None else gold
    manifest_input = manifest_path if manifest_path is not None else manifest
    suite_path = Path(suite_input) if suite_input is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite.jsonl"
    gold_path = Path(gold_input) if gold_input is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl"
    manifest_path = Path(manifest_input) if manifest_input is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_manifest.json"
    reports_dir = Path(report_dir) if report_dir is not None else DEFAULT_CONFIG.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    warnings: list[str] = []
    runtime_rows = _read_jsonl(suite_path, errors, "runtime")
    gold_rows = _read_jsonl(gold_path, errors, "gold")
    manifest_payload: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"manifest_json_invalid:{type(exc).__name__}")
    else:
        errors.append("manifest_missing")

    runtime_ids = [str(row.get("prompt_id")) for row in runtime_rows]
    gold_ids = [str(row.get("prompt_id")) for row in gold_rows]
    runtime_by_id = {row.get("prompt_id"): row for row in runtime_rows}
    gold_by_id = {row.get("prompt_id"): row for row in gold_rows}

    runtime_gold_leaks = _runtime_gold_leaks(runtime_rows)
    private_cot = _private_reasoning_hits(runtime_rows, gold_rows)
    secret_hits = _secret_hits(runtime_rows, gold_rows, manifest_payload)
    duplicate_prompts = _duplicates(normalize_prompt_text(str(row.get("prompt", ""))) for row in runtime_rows)
    duplicate_ids = _duplicates(runtime_ids)
    category_counts = Counter(str(row.get("category")) for row in runtime_rows)
    signature_counts = _semantic_signature_counts(gold_rows)
    expected_trace_missing = [row.get("prompt_id") for row in gold_rows if not row.get("expected_observable_trace")]
    oracle_gaps = _oracle_gaps(gold_rows)
    oracle_sql_checks = _validate_oracle_sql(gold_rows)
    endpoint_checks = _validate_expected_endpoints(gold_rows)
    synthetic_artifacts = _synthetic_prompt_artifacts(runtime_rows)

    if len(runtime_rows) != 500:
        errors.append(f"runtime_count_expected_500_actual_{len(runtime_rows)}")
    if len(gold_rows) != 500:
        errors.append(f"gold_count_expected_500_actual_{len(gold_rows)}")
    if set(runtime_ids) != set(gold_ids):
        errors.append("prompt_id_mismatch_between_runtime_and_gold")
    if duplicate_ids:
        errors.append("duplicate_prompt_ids")
    if duplicate_prompts:
        errors.append("duplicate_normalized_prompts")
    if runtime_gold_leaks:
        errors.append("runtime_gold_field_leakage")
    if private_cot:
        errors.append("private_chain_of_thought_detected")
    if secret_hits:
        errors.append("secret_like_value_detected")
    if expected_trace_missing:
        errors.append("expected_observable_trace_missing")
    if oracle_gaps:
        errors.append("oracle_evidence_gaps")
    if oracle_sql_checks["oracle_sql_reexecution_failures"]:
        errors.append("oracle_sql_reexecution_failures")
    if endpoint_checks["endpoint_catalog_validation_failures"]:
        errors.append("endpoint_catalog_validation_failures")
    if dict(category_counts) != CATEGORY_TARGETS:
        errors.append("category_distribution_mismatch")
    if any(count > 1 for count in signature_counts.values()):
        errors.append("duplicate_semantic_signatures")

    for row in runtime_rows:
        missing = REQUIRED_RUNTIME_FIELDS - set(row)
        if missing:
            errors.append(f"runtime_missing_fields:{row.get('prompt_id')}:{sorted(missing)}")
        extra_gold = sorted(set(row) & RUNTIME_GOLD_FORBIDDEN)
        if extra_gold:
            errors.append(f"runtime_contains_gold_fields:{row.get('prompt_id')}:{extra_gold}")
    for row in gold_rows:
        missing = REQUIRED_GOLD_FIELDS - set(row)
        if missing:
            errors.append(f"gold_missing_fields:{row.get('prompt_id')}:{sorted(missing)}")
        tool_calls = row.get("expected_tool_calls") if isinstance(row.get("expected_tool_calls"), dict) else {}
        if tool_calls.get("sql_required") and not (row.get("oracle_evidence") or {}).get("oracle_sql"):
            errors.append(f"sql_required_without_oracle_sql:{row.get('prompt_id')}")
        if (tool_calls.get("api_required") or tool_calls.get("api_optional")) and not (row.get("oracle_evidence") or {}).get("oracle_api_endpoint"):
            errors.append(f"api_expected_without_oracle_endpoint:{row.get('prompt_id')}")
        if row.get("gold_answer_type") == "conceptual_rubric":
            text = json.dumps(
                {
                    "gold_answer": row.get("gold_answer"),
                    "acceptable_answer_variants": row.get("acceptable_answer_variants"),
                    "required_facts": row.get("required_facts"),
                },
                sort_keys=True,
            ).lower()
            if re.search(r"\b\d{4}-\d{2}-\d{2}\b|[0-9a-f]{8}-[0-9a-f]{4}-|\b[a-z0-9]{12,}\b", text):
                errors.append(f"conceptual_concrete_claim_risk:{row.get('prompt_id')}")

    summary = {
        "ok": not errors,
        "suite": str(suite_path),
        "gold": str(gold_path),
        "manifest": str(manifest_path),
        "total_prompts": len(runtime_rows),
        "total_runtime_rows": len(runtime_rows),
        "total_gold_rows": len(gold_rows),
        "prompt_id_match": set(runtime_ids) == set(gold_ids),
        "category_counts": dict(category_counts),
        "expected_category_counts": CATEGORY_TARGETS,
        "runtime_gold_leak_count": len(runtime_gold_leaks),
        "runtime_gold_field_leak_count": len(runtime_gold_leaks),
        "runtime_gold_leaks": runtime_gold_leaks[:20],
        "private_chain_of_thought_count": len(private_cot),
        "private_chain_of_thought_hits": private_cot[:20],
        "secret_hit_count": len(secret_hits),
        "secret_hits": secret_hits[:20],
        "duplicate_prompt_count": len(duplicate_prompts),
        "duplicate_id_count": len(duplicate_ids),
        "semantic_signature_duplicate_count": sum(max(0, count - 1) for count in signature_counts.values()),
        "expected_trace_missing_count": len(expected_trace_missing),
        "oracle_gap_count": len(oracle_gaps),
        "oracle_gaps": oracle_gaps[:20],
        **oracle_sql_checks,
        **endpoint_checks,
        "synthetic_prompt_artifact_count": len(synthetic_artifacts),
        "synthetic_prompt_artifacts": synthetic_artifacts[:30],
        "errors": errors,
        "warnings": warnings,
        "diagnostic_internal_only": True,
        "organizer_score_replacement": False,
        "runtime_gold_separated": not runtime_gold_leaks,
    }

    report_json_path = reports_dir / "dashagent_500_prompt_suite_validation.json"
    report_md_path = reports_dir / "dashagent_500_prompt_suite_validation.md"
    report_json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_validation_md(summary), encoding="utf-8")
    return summary


def _read_jsonl(path: Path, errors: list[str], label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        errors.append(f"{label}_missing:{path}")
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception as exc:
            errors.append(f"{label}_jsonl_invalid:{line_no}:{type(exc).__name__}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{label}_jsonl_non_object:{line_no}")
            continue
        rows.append(payload)
    return rows


def _runtime_gold_leaks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leaks: list[dict[str, Any]] = []
    for row in rows:
        fields = sorted(set(row) & RUNTIME_GOLD_FORBIDDEN)
        if fields:
            leaks.append({"prompt_id": row.get("prompt_id"), "fields": fields})
    return leaks


def _private_reasoning_hits(runtime_rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for label, rows in [("runtime", runtime_rows), ("gold", gold_rows)]:
        for row in rows:
            text = json.dumps(row, sort_keys=True)
            if PRIVATE_REASONING_PATTERNS.search(text):
                hits.append({"source": label, "prompt_id": row.get("prompt_id")})
    return hits


def _secret_hits(runtime_rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for label, payload in [("runtime", runtime_rows), ("gold", gold_rows), ("manifest", manifest)]:
        text = json.dumps(payload, sort_keys=True)
        if SECRET_PATTERNS.search(text):
            hits.append({"source": label, "pattern": "secret_like_value"})
    return hits


def _duplicates(values: Any) -> list[str]:
    counter = Counter(values)
    return [value for value, count in counter.items() if count > 1]


def _semantic_signature_counts(gold_rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(json.dumps(row.get("semantic_signature", {}), sort_keys=True) for row in gold_rows)


def _oracle_gaps(gold_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for row in gold_rows:
        tools = row.get("expected_tool_calls") if isinstance(row.get("expected_tool_calls"), dict) else {}
        evidence = row.get("oracle_evidence") if isinstance(row.get("oracle_evidence"), dict) else {}
        if tools.get("sql_required") and not evidence.get("oracle_sql"):
            gaps.append({"prompt_id": row.get("prompt_id"), "gap": "missing_oracle_sql"})
        if (tools.get("api_required") or tools.get("api_optional")) and not evidence.get("oracle_api_endpoint"):
            gaps.append({"prompt_id": row.get("prompt_id"), "gap": "missing_oracle_api_endpoint"})
    return gaps


def _validate_oracle_sql(gold_rows: list[dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    failures: list[dict[str, Any]] = []
    db: DuckDBDatabase | None = None
    try:
        db = DuckDBDatabase()
    except Exception as exc:
        return {
            "oracle_sql_reexecution_checked": 0,
            "oracle_sql_reexecution_failures": [{"prompt_id": None, "error": f"duckdb_init_failed:{type(exc).__name__}"}],
            "oracle_sql_read_only_failures": [],
            "oracle_sql_expected_table_failures": [],
        }

    read_only_failures: list[dict[str, Any]] = []
    table_failures: list[dict[str, Any]] = []
    try:
        for row in gold_rows:
            evidence = row.get("oracle_evidence") if isinstance(row.get("oracle_evidence"), dict) else {}
            oracle_sql = evidence.get("oracle_sql")
            if not oracle_sql:
                continue
            prompt_id = row.get("prompt_id")
            checked += 1
            ok, error = is_read_only_sql(str(oracle_sql))
            if not ok:
                read_only_failures.append({"prompt_id": prompt_id, "error": error})
                continue
            expected_tables = ((row.get("expected_tool_calls") or {}).get("expected_sql_tables") or [])
            normalized_sql = str(oracle_sql).lower()
            missing_tables = [table for table in expected_tables if str(table).lower() not in normalized_sql]
            if missing_tables:
                table_failures.append({"prompt_id": prompt_id, "missing_tables": missing_tables})
            result = db.execute_sql(str(oracle_sql), max_rows=5)
            if not result.get("ok"):
                failures.append({"prompt_id": prompt_id, "error": result.get("error")})
    finally:
        if db is not None:
            db.close()
    return {
        "oracle_sql_reexecution_checked": checked,
        "oracle_sql_reexecution_failures": failures[:50],
        "oracle_sql_read_only_failures": read_only_failures[:50],
        "oracle_sql_expected_table_failures": table_failures[:50],
    }


def _validate_expected_endpoints(gold_rows: list[dict[str, Any]]) -> dict[str, Any]:
    catalog = EndpointCatalog()
    failures: list[dict[str, Any]] = []
    checked = 0
    for row in gold_rows:
        expected_tools = row.get("expected_tool_calls") if isinstance(row.get("expected_tool_calls"), dict) else {}
        endpoint_ids = set(expected_tools.get("expected_api_families") or [])
        evidence = row.get("oracle_evidence") if isinstance(row.get("oracle_evidence"), dict) else {}
        if evidence.get("oracle_api_endpoint"):
            endpoint_ids.add(str(evidence["oracle_api_endpoint"]))
        for endpoint_id in sorted(endpoint_ids):
            checked += 1
            endpoint = catalog.by_id(endpoint_id)
            if endpoint is None:
                failures.append({"prompt_id": row.get("prompt_id"), "endpoint_id": endpoint_id, "error": "missing_from_endpoint_catalog"})
                continue
            if endpoint.method.upper() != "GET":
                failures.append({"prompt_id": row.get("prompt_id"), "endpoint_id": endpoint_id, "error": "non_get_endpoint"})
            if endpoint.path_params and row.get("gold_answer_type") != "caveat":
                failures.append({"prompt_id": row.get("prompt_id"), "endpoint_id": endpoint_id, "error": "requires_path_param_without_caveat"})
    return {
        "endpoint_catalog_validation_checked": checked,
        "endpoint_catalog_validation_failures": failures[:50],
    }


def _synthetic_prompt_artifacts(runtime_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"\b(?:concept|sql|api|policy|mixed|ambiguous|stress)\s+case\s+\d+\b|"
        r"\b(?:case|trigger)\s+\d+\b",
        re.IGNORECASE,
    )
    artifacts: list[dict[str, Any]] = []
    for row in runtime_rows:
        prompt = str(row.get("prompt") or "")
        if pattern.search(prompt):
            artifacts.append({"prompt_id": row.get("prompt_id"), "prompt": prompt})
    return artifacts


def _validation_md(summary: dict[str, Any]) -> str:
    lines = [
        "# DashAgent 500-Prompt Suite Validation",
        "",
        f"- ok: {str(summary['ok']).lower()}",
        f"- total_runtime_rows: {summary['total_runtime_rows']}",
        f"- total_gold_rows: {summary['total_gold_rows']}",
        f"- runtime_gold_leak_count: {summary['runtime_gold_leak_count']}",
        f"- private_chain_of_thought_count: {summary['private_chain_of_thought_count']}",
        f"- secret_hit_count: {summary['secret_hit_count']}",
        f"- duplicate_prompt_count: {summary['duplicate_prompt_count']}",
        f"- oracle_sql_reexecution_checked: {summary['oracle_sql_reexecution_checked']}",
        f"- oracle_sql_reexecution_failures: {len(summary['oracle_sql_reexecution_failures'])}",
        f"- endpoint_catalog_validation_failures: {len(summary['endpoint_catalog_validation_failures'])}",
        f"- synthetic_prompt_artifact_count: {summary['synthetic_prompt_artifact_count']}",
        f"- semantic_signature_duplicate_count: {summary['semantic_signature_duplicate_count']}",
        "",
        "## Category Counts",
    ]
    for category, count in summary["category_counts"].items():
        lines.append(f"- {category}: {count}")
    if summary["errors"]:
        lines.extend(["", "## Errors"])
        for error in summary["errors"][:80]:
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the internal DashAgent 500-prompt benchmark suite.")
    parser.add_argument("--suite", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite.jsonl")
    parser.add_argument("--gold", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_manifest.json")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_CONFIG.outputs_dir / "reports")
    args = parser.parse_args()
    summary = validate_suite(suite=args.suite, gold=args.gold, manifest=args.manifest, report_dir=args.report_dir)
    print(json.dumps({"ok": summary["ok"], "errors": summary["errors"][:10]}, sort_keys=True))
    raise SystemExit(0 if summary["ok"] else 1)


if __name__ == "__main__":
    main()
