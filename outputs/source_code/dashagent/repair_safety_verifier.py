from __future__ import annotations

from typing import Any

from .api_endpoint_repair import repair_api_call
from .endpoint_catalog import EndpointCatalog, normalize_api_path
from .schema_index import SchemaIndex
from .sql_ast_tools import sql_ast_summary
from .validators import APIValidator, SQLValidator


def verify_repair_safety(
    current_plan: dict[str, Any],
    repaired_plan: dict[str, Any],
    trajectory: dict[str, Any],
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
) -> dict[str, Any]:
    """Conservatively decide whether a shadow repair could be canaried.

    This verifier is intentionally stricter than the report-only ranker.  A
    failed or missing diagnostic leaves the repair unsafe, because the packaged
    strategy must not change unless the what-if path is both validated and
    deterministic.
    """

    reasons: list[str] = []
    failed_checks: list[str] = []

    sql_validator = SQLValidator(schema_index, enable_ast_validation=True)
    api_validator = APIValidator(endpoint_catalog)

    sql_results = _validate_sql(repaired_plan.get("sql") or [], sql_validator, schema_index)
    if not sql_results["ok"]:
        failed_checks.append("sql_validation")
        reasons.extend(sql_results["errors"])

    api_results = _validate_api(repaired_plan.get("api_calls") or [], api_validator, endpoint_catalog)
    if not api_results["ok"]:
        failed_checks.append("api_validation")
        reasons.extend(api_results["errors"])

    current_tools = int(current_plan.get("tool_call_count") or 0)
    repaired_tools = int(repaired_plan.get("tool_call_count") or 0)
    if repaired_tools > current_tools:
        failed_checks.append("tool_call_increase")
        reasons.append(f"Repaired plan would increase tool calls from {current_tools} to {repaired_tools}.")

    endpoint_confidence = float(repaired_plan.get("endpoint_family_confidence") or 0.0)
    if repaired_plan.get("api_calls") and endpoint_confidence < 0.75:
        failed_checks.append("endpoint_family_confidence")
        reasons.append(f"Endpoint family confidence {endpoint_confidence:.4f} is below 0.75.")

    if repaired_plan.get("fusion_agreement") is not True:
        failed_checks.append("fusion_agreement")
        reasons.append("Weighted score fusion and reciprocal-rank/family diagnostics did not agree.")

    current_shape = current_plan.get("expected_answer_shape")
    repaired_shape = repaired_plan.get("expected_answer_shape")
    if current_shape and repaired_shape and current_shape != repaired_shape and not repaired_plan.get("answer_shape_more_specific"):
        failed_checks.append("answer_shape")
        reasons.append("Expected answer shape changed without a more-specific-shape marker.")

    if repaired_plan.get("dry_run_only") and repaired_plan.get("live_api_evidence_available"):
        failed_checks.append("dry_run_live_evidence")
        reasons.append("Dry-run API output was marked as live API evidence.")

    unsupported = _unsupported_claim_count(trajectory)
    if unsupported > 0:
        failed_checks.append("unsupported_claims")
        reasons.append(f"Existing final answer verifier reported {unsupported} unsupported claim(s).")

    safe = not failed_checks
    confidence_parts = [
        1.0 if sql_results["ok"] else 0.0,
        1.0 if api_results["ok"] else 0.0,
        min(1.0, endpoint_confidence) if repaired_plan.get("api_calls") else 1.0,
        1.0 if repaired_plan.get("fusion_agreement") is True else 0.0,
        1.0 if repaired_tools <= current_tools else 0.0,
    ]
    confidence = round(sum(confidence_parts) / len(confidence_parts), 4)
    if safe:
        reasons.append("Repair passed conservative SQL/API, fusion, evidence, and cost checks.")
    return {
        "safe": safe,
        "reasons": reasons,
        "failed_checks": sorted(set(failed_checks)),
        "confidence": confidence,
        "sql_validation": sql_results,
        "api_validation": api_results,
        "correctness_role": "guards repaired plans against schema/API mismatch and unsupported evidence claims",
        "efficiency_role": "rejects repairs that increase packaged tool-call cost",
    }


def _validate_sql(sql_values: list[Any], validator: SQLValidator, schema_index: SchemaIndex) -> dict[str, Any]:
    errors: list[str] = []
    summaries: list[dict[str, Any]] = []
    for sql in sql_values:
        sql_text = str(sql or "").strip()
        if not sql_text:
            continue
        validation = validator.validate(sql_text)
        ast = sql_ast_summary(sql_text, schema_index)
        summaries.append(ast)
        if not validation.ok:
            errors.extend(validation.errors)
        if ast.get("parse_error"):
            errors.append(f"SQLGlot parse error: {ast.get('parse_error')}")
        if ast.get("destructive_sql_detected"):
            errors.append("SQLGlot detected destructive SQL.")
        if ast.get("unknown_tables"):
            errors.append(f"Unknown tables: {', '.join(ast.get('unknown_tables') or [])}")
        if ast.get("unknown_columns"):
            errors.append(f"Unknown columns: {', '.join(ast.get('unknown_columns') or [])}")
    return {"ok": not errors, "errors": sorted(set(errors)), "ast_summaries": summaries}


def _validate_api(
    calls: list[dict[str, Any]],
    validator: APIValidator,
    endpoint_catalog: EndpointCatalog,
) -> dict[str, Any]:
    errors: list[str] = []
    repaired_aliases: list[dict[str, Any]] = []
    for call in calls:
        method = str(call.get("method") or "GET").upper()
        url = str(call.get("path") or call.get("url") or "")
        params = dict(call.get("params") or {})
        validation = validator.validate(method, url, params, dict(call.get("headers") or {}))
        if validation.ok:
            continue
        repair = repair_api_call(method, url, params, endpoint_catalog)
        if repair.get("repaired"):
            repaired_aliases.append(repair)
            repaired_validation = validator.validate(method, repair["url"], repair.get("params", {}), {})
            if repaired_validation.ok:
                continue
        normalized = normalize_api_path(url)
        errors.append(f"Invalid repaired endpoint: {method} {normalized}; {'; '.join(validation.errors)}")
    return {"ok": not errors, "errors": sorted(set(errors)), "repaired_aliases": repaired_aliases}


def _unsupported_claim_count(trajectory: dict[str, Any]) -> int:
    for checkpoint in trajectory.get("checkpoints", []) or []:
        if checkpoint.get("checkpoint_id") != "checkpoint_16_answer_verification":
            continue
        output = checkpoint.get("output") or {}
        try:
            return int(output.get("unsupported_claims_count") or 0)
        except Exception:
            return 0
    return 0
