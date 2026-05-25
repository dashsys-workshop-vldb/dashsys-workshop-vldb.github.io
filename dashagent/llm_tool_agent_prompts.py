from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .trajectory import compact_preview, redact_secrets


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str


def build_planning_prompt(prompt: str, context: dict[str, Any]) -> PromptBundle:
    return PromptBundle(
        system_prompt=(
            "You are a DASHSys pure LLM tool planner. Return JSON only. "
            "Do not call tools in this step. Required keys: "
            '"answer_intent", "needs_sql", "needs_api", "reason", "candidate_tables", '
            '"candidate_endpoints", "sql_task", "api_task", "answer_shape".'
        ),
        user_prompt=json.dumps(
            {"prompt": prompt, "schema_and_endpoint_context": compact_preview(context, 7000)},
            indent=2,
            default=str,
        ),
    )


def build_sql_candidate_prompt(prompt: str, context: dict[str, Any], plan: dict[str, Any] | None = None) -> PromptBundle:
    return PromptBundle(
        system_prompt=(
            "Generate one read-only DuckDB SQL candidate. Return JSON only with keys: "
            '"sql", "tables_used", "columns_used", "join_reason", "aggregation", "filters", "confidence". '
            "The sql value is required and must be a SELECT query. Do not answer in prose. "
            "Use only tables/columns in the supplied context. For list/status/date tasks, select concrete columns "
            "from the most relevant table and add a conservative LIMIT. For count tasks, return a COUNT expression."
        ),
        user_prompt=json.dumps(
            {"prompt": prompt, "plan": plan or {}, "schema_context": compact_preview(context, 9000)},
            indent=2,
            default=str,
        ),
    )


def build_sql_repair_prompt(
    prompt: str,
    context: dict[str, Any],
    bad_sql: str,
    validation_errors: list[str],
) -> PromptBundle:
    return PromptBundle(
        system_prompt=(
            "Repair invalid read-only DuckDB SQL. Return JSON only with the same SQL candidate schema. "
            "The sql value is required and must be a SELECT query. Use only supplied tables and columns. "
            "Do not explain outside JSON."
        ),
        user_prompt=json.dumps(
            {
                "prompt": prompt,
                "bad_sql": bad_sql,
                "validation_errors": validation_errors,
                "schema_context": compact_preview(context, 9000),
            },
            indent=2,
            default=str,
        ),
    )


def build_api_candidate_prompt(prompt: str, context: dict[str, Any], plan: dict[str, Any] | None = None) -> PromptBundle:
    return PromptBundle(
        system_prompt=(
            "Choose one Adobe API endpoint from the catalog candidates. Return JSON only with keys: "
            '"endpoint_id", "method", "params", "reason". Use method GET unless the catalog explicitly says otherwise. '
            "Do not choose endpoints with unresolved path parameters such as {id} unless the prompt supplies that exact value."
        ),
        user_prompt=json.dumps(
            {"prompt": prompt, "plan": plan or {}, "endpoint_candidates": context.get("endpoint_candidates", [])},
            indent=2,
            default=str,
        ),
    )


def build_final_answer_prompt(
    prompt: str,
    observations: list[dict[str, Any]],
    *,
    answer_intent: str | None = None,
) -> PromptBundle:
    return PromptBundle(
        system_prompt=(
            "Write the final answer from tool observations only. Return JSON only with keys: "
            '"answer", "claims", "uncertainties". Each claim must include evidence_source and evidence_field. '
            "Do not invent counts, names, IDs, statuses, timestamps, API success, or empty-result conclusions."
        ),
        user_prompt=json.dumps(
            {
                "prompt": prompt,
                "answer_intent": answer_intent,
                "tool_observations": compact_preview(observations, 8000),
            },
            indent=2,
            default=str,
        ),
    )


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
        return redact_secrets(parsed) if isinstance(parsed, dict) else {}
    except Exception:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return redact_secrets(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            return {}
