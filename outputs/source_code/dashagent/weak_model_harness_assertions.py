from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .trajectory import redact_secrets


@dataclass(frozen=True)
class HarnessAssertionResult:
    assertion_id: str
    passed: bool
    failure_reason: str
    repair_hint: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HarnessAssertionReport:
    def __init__(self, results: list[HarnessAssertionResult]) -> None:
        self.results = results

    def failed(self, assertion_id: str) -> bool:
        return any(item.assertion_id == assertion_id and not item.passed for item in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {"results": [item.to_dict() for item in self.results], "failed_assertions": [item.assertion_id for item in self.results if not item.passed]}


ASSERTION_CATALOG: list[dict[str, str]] = [
    {"assertion_id": "data_question_requires_tool", "severity": "fatal", "repair_hint": "Use execute_sql or call_api before answering data questions."},
    {"assertion_id": "sql_required_has_candidate", "severity": "recoverable", "repair_hint": "Produce a SQL candidate or explicit no-SQL reason."},
    {"assertion_id": "api_required_has_candidate", "severity": "recoverable", "repair_hint": "Choose a valid endpoint catalog candidate."},
    {"assertion_id": "sql_preconditions_before_execution", "severity": "fatal", "repair_hint": "Retrieve schema context, pass unit tests, pass SQLValidator, and parse SQL before execution."},
    {"assertion_id": "api_endpoint_catalog_valid", "severity": "fatal", "repair_hint": "Use a known GET endpoint without unresolved path parameters."},
    {"assertion_id": "api_no_unresolved_path_params", "severity": "fatal", "repair_hint": "Resolve path parameters through safe discovery or choose another endpoint."},
    {"assertion_id": "final_claims_supported", "severity": "fatal", "repair_hint": "Remove unsupported claims or render only EvidenceBus facts."},
    {"assertion_id": "sql_evidence_used_when_answering", "severity": "recoverable", "repair_hint": "Use direct SQL evidence in the final answer."},
    {"assertion_id": "api_evidence_used_when_required", "severity": "recoverable", "repair_hint": "Use required API evidence in the final answer."},
    {"assertion_id": "live_empty_not_global_no_data", "severity": "fatal", "repair_hint": "Treat live_empty as endpoint/context empty, not global no-data."},
    {"assertion_id": "api_error_not_no_data", "severity": "fatal", "repair_hint": "Treat api_error as unavailable evidence, not no data."},
]


def evaluate_harness_assertions(trace: dict[str, Any]) -> HarnessAssertionReport:
    slots = trace.get("semantic_slots") if isinstance(trace.get("semantic_slots"), dict) else {}
    evidence_need = str(slots.get("evidence_need") or trace.get("evidence_need") or "").lower()
    intent = str(slots.get("intent") or "").upper()
    domain = str(slots.get("domain") or "").upper()
    tool_calls = trace.get("tool_calls") if isinstance(trace.get("tool_calls"), list) else []
    answer = str(trace.get("answer") or "")
    results = []

    data_question = intent in {"COUNT", "LIST", "STATUS", "DATE", "DETAIL", "RELATIONSHIP"} and domain != "UNKNOWN"
    results.append(_result("data_question_requires_tool", (not data_question) or bool(tool_calls), "Data question answered without tool evidence."))

    sql_required = evidence_need in {"sql_first", "sql_only", "sql_then_api", "sql_primary_api_verify"}
    has_sql_candidate = bool(trace.get("sql_candidate") or trace.get("compiled_sql") or trace.get("sql_no_answer_reason"))
    results.append(_result("sql_required_has_candidate", (not sql_required) or has_sql_candidate, "SQL-required plan has no SQL candidate or no-SQL reason."))

    api_required = evidence_need in {"api_first", "api_only", "api_then_sql", "api_primary_sql_context", "sql_then_api"}
    has_api_candidate = bool(trace.get("api_candidate") or trace.get("api_no_answer_reason"))
    results.append(_result("api_required_has_candidate", (not api_required) or has_api_candidate, "API-required plan has no API candidate."))

    sql_exec = bool(trace.get("sql_executed"))
    sql_ok = bool(trace.get("schema_context")) and _truthy_path(trace, "sql_unit_tests", "passed") and _truthy_path(trace, "sql_validation", "ok") and not trace.get("sqlglot_parse_error")
    results.append(_result("sql_preconditions_before_execution", (not sql_exec) or sql_ok, "SQL execution happened before harness preconditions passed."))

    api_candidate = trace.get("api_candidate") if isinstance(trace.get("api_candidate"), dict) else {}
    api_known = not api_candidate or bool(api_candidate.get("endpoint_id"))
    results.append(_result("api_endpoint_catalog_valid", api_known and str(api_candidate.get("method") or "GET").upper() == "GET", "API candidate is not a known GET catalog endpoint."))
    path = str(api_candidate.get("path") or api_candidate.get("url") or "")
    results.append(_result("api_no_unresolved_path_params", "{" not in path and "}" not in path, "API candidate has unresolved path parameters."))

    unsupported = int(trace.get("unsupported_claim_count") or 0)
    results.append(_result("final_claims_supported", unsupported == 0, "Final answer has unsupported claims."))

    sql_evidence = trace.get("sql_evidence") if isinstance(trace.get("sql_evidence"), dict) else {}
    sql_direct = bool(sql_evidence.get("sql_executed") and (sql_evidence.get("count_value") is not None or sql_evidence.get("rows_preview") or sql_evidence.get("key_names")))
    results.append(_result("sql_evidence_used_when_answering", (not sql_direct) or bool(trace.get("answer_used_sql")) or _answer_mentions_evidence(answer, sql_evidence), "Final answer did not use direct SQL evidence."))

    api_evidence = trace.get("api_evidence") if isinstance(trace.get("api_evidence"), dict) else {}
    results.append(_result("api_evidence_used_when_required", (not api_required) or not api_evidence or bool(trace.get("answer_used_api")) or _answer_mentions_evidence(answer, api_evidence), "Final answer did not use required API evidence."))

    api_outcome = str((trace.get("api_evidence") or {}).get("outcome") or (trace.get("api_evidence") or {}).get("evidence_state") or "").lower()
    global_no_data = any(text in answer.lower() for text in ("no data in adobe", "no data exists", "no records exist anywhere"))
    results.append(_result("live_empty_not_global_no_data", not (api_outcome == "live_empty" and global_no_data), "live_empty was worded as global no-data."))
    results.append(_result("api_error_not_no_data", not (api_outcome == "api_error" and "no data" in answer.lower()), "api_error was worded as no data."))

    return HarnessAssertionReport(results)


def assertion_catalog_payload() -> dict[str, Any]:
    return {"report_type": "weak_model_harness_assertion_catalog", "assertions": ASSERTION_CATALOG}


def write_assertion_catalog(reports_dir: Path) -> None:
    payload = assertion_catalog_payload()
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "weak_model_harness_assertion_catalog.json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True), encoding="utf-8")
    lines = ["# Weak Model Harness Assertion Catalog", "", "| Assertion | Severity | Repair hint |", "| --- | --- | --- |"]
    for item in ASSERTION_CATALOG:
        lines.append(f"| `{item['assertion_id']}` | `{item['severity']}` | {item['repair_hint']} |")
    (reports_dir / "weak_model_harness_assertion_catalog.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _result(assertion_id: str, passed: bool, failure_reason: str) -> HarnessAssertionResult:
    catalog = next(item for item in ASSERTION_CATALOG if item["assertion_id"] == assertion_id)
    return HarnessAssertionResult(assertion_id, bool(passed), "" if passed else failure_reason, catalog["repair_hint"], catalog["severity"])


def _truthy_path(payload: dict[str, Any], parent: str, key: str) -> bool:
    value = payload.get(parent) if isinstance(payload.get(parent), dict) else {}
    return bool(value.get(key))


def _answer_mentions_evidence(answer: str, evidence: dict[str, Any]) -> bool:
    lowered = answer.lower()
    for key in ("count_value", "key_names", "key_ids", "names", "ids", "statuses", "timestamp_values"):
        value = evidence.get(key)
        values = value if isinstance(value, list) else [value]
        for item in values:
            if item is not None and str(item).strip() and str(item).lower() in lowered:
                return True
    return False
