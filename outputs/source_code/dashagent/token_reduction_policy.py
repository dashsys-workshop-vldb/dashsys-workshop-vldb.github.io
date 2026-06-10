from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from .trajectory import estimate_tokens


@dataclass(frozen=True)
class TokenReductionPolicy:
    max_preview_rows: int = 1
    max_cell_chars: int = 96
    max_text_chars: int = 160
    max_list_items: int = 3
    max_checkpoint_fields: int = 12
    max_reason_chars: int = 96


DEFAULT_TOKEN_REDUCTION_POLICY = TokenReductionPolicy()
REQUIRED_TRAJECTORY_FIELDS = {"final_answer", "tool_call_count", "runtime", "estimated_tokens"}


def official_estimated_tokens(trajectory: dict[str, Any]) -> int:
    token_steps = [step for step in trajectory.get("steps", []) if step.get("kind") != "answer_diagnostics"]
    return estimate_tokens(
        {
            "query": trajectory.get("original_query"),
            "steps": token_steps,
            "answer": trajectory.get("final_answer"),
        }
    )


def summarize_reducible_text(text: Any, max_chars: int) -> Any:
    if not isinstance(text, str) or len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 16)].rstrip() + " [truncated]"


def compact_preview_rows(rows: Any, max_rows: int, max_cell_chars: int) -> Any:
    if isinstance(rows, list):
        return [_compact_row(row, max_cell_chars) for row in rows[:max_rows]]
    if isinstance(rows, dict) and isinstance(rows.get("items"), list):
        compacted = dict(rows)
        compacted["items"] = [_compact_row(row, max_cell_chars) for row in rows.get("items", [])[:max_rows]]
        if rows.get("total_items", len(rows.get("items", []))) > len(compacted["items"]):
            compacted["truncated_items"] = True
        return compacted
    return rows


def compact_step_payload(
    step: dict[str, Any],
    policy: TokenReductionPolicy = DEFAULT_TOKEN_REDUCTION_POLICY,
    *,
    path: str = "step",
    reduced_fields: list[str] | None = None,
) -> dict[str, Any]:
    fields = reduced_fields if reduced_fields is not None else []
    compacted = copy.deepcopy(step)
    kind = compacted.get("kind")
    if kind == "route":
        _replace_if_changed(compacted, "candidate_apis", _compact_candidate_apis(compacted.get("candidate_apis"), policy), f"{path}.candidate_apis", fields)
        _replace_if_changed(compacted, "candidate_tables", _limit_list(compacted.get("candidate_tables"), policy.max_list_items), f"{path}.candidate_tables", fields)
        _replace_if_changed(compacted, "reason", summarize_reducible_text(compacted.get("reason"), policy.max_reason_chars), f"{path}.reason", fields)
    elif kind == "nlp":
        _compact_nlp_step(compacted, policy, path, fields)
    elif kind == "metadata":
        metadata_path = compacted.get("metadata_path")
        if isinstance(metadata_path, str) and len(metadata_path) > 32:
            compacted["metadata_path"] = "metadata.json"
            fields.append(f"{path}.metadata_path")
    elif kind == "plan":
        _replace_if_changed(compacted, "rationale", summarize_reducible_text(compacted.get("rationale"), policy.max_reason_chars), f"{path}.rationale", fields)
        _replace_if_changed(compacted, "optimizer_actions", _dedupe_short_list(compacted.get("optimizer_actions"), 2), f"{path}.optimizer_actions", fields)
        _replace_if_changed(compacted, "steps", _compact_plan_steps(compacted.get("steps")), f"{path}.steps", fields)
    elif kind == "optimizer":
        ensemble = compacted.get("plan_ensemble")
        if isinstance(ensemble, dict):
            for key in ["candidate_scores", "candidate_tool_calls"]:
                if isinstance(ensemble.get(key), dict) and len(ensemble[key]) > policy.max_list_items:
                    ensemble[key] = dict(list(ensemble[key].items())[: policy.max_list_items])
                    fields.append(f"{path}.plan_ensemble.{key}")
        _replace_if_changed(compacted, "actions", _dedupe_short_list(compacted.get("actions"), policy.max_list_items), f"{path}.actions", fields)
    elif kind == "sql_call":
        _compact_validation(compacted.get("validation"), policy, f"{path}.validation", fields)
        _compact_tool_result(compacted.get("result"), policy, f"{path}.result", fields)
    elif kind == "api_call":
        _compact_validation(compacted.get("validation"), policy, f"{path}.validation", fields)
        _compact_tool_result(compacted.get("result"), policy, f"{path}.result", fields)
    return compacted


def compact_checkpoint_payload(
    checkpoint: dict[str, Any],
    policy: TokenReductionPolicy = DEFAULT_TOKEN_REDUCTION_POLICY,
    *,
    path: str = "checkpoint",
    reduced_fields: list[str] | None = None,
) -> dict[str, Any]:
    fields = reduced_fields if reduced_fields is not None else []
    compacted = _compact_generic(copy.deepcopy(checkpoint), policy, path, fields)
    return compacted if isinstance(compacted, dict) else checkpoint


def apply_token_reduction_to_trajectory(
    trajectory: dict[str, Any],
    policy: TokenReductionPolicy = DEFAULT_TOKEN_REDUCTION_POLICY,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reduced = copy.deepcopy(trajectory)
    before = _serialized_official_estimated_tokens(reduced)
    reduced_fields: list[str] = []
    reduced["steps"] = [
        compact_step_payload(step, policy, path=f"steps[{index}]", reduced_fields=reduced_fields)
        for index, step in enumerate(reduced.get("steps", []))
    ]
    checkpoint_fields: list[str] = []
    reduced["checkpoints"] = [
        compact_checkpoint_payload(checkpoint, policy, path=f"checkpoints[{index}]", reduced_fields=checkpoint_fields)
        for index, checkpoint in enumerate(reduced.get("checkpoints", []))
    ]
    after = _serialized_official_estimated_tokens(reduced)
    reduced["estimated_tokens"] = after
    summary = {
        "active": True,
        "reduced_fields": sorted(set(reduced_fields)),
        "checkpoint_reduced_fields": sorted(set(checkpoint_fields)),
        "estimated_tokens_before": before,
        "estimated_tokens_after": after,
        "expected_savings": before - after,
        "packaged_execution_changed": False,
        "correctness_impact_expected": False,
    }
    checkpoint = {
        "checkpoint_id": "checkpoint_official_token_reduction",
        "active": True,
        "reduced_fields": summary["reduced_fields"][: policy.max_checkpoint_fields],
        "estimated_tokens_before": before,
        "estimated_tokens_after": after,
        "expected_savings": before - after,
        "packaged_execution_changed": False,
        "correctness_impact_expected": False,
    }
    reduced.setdefault("checkpoints", []).append(checkpoint)
    return reduced, summary


def _compact_candidate_apis(value: Any, policy: TokenReductionPolicy) -> Any:
    if not isinstance(value, list):
        return value
    compacted = []
    for item in value[: policy.max_list_items]:
        if isinstance(item, dict):
            compacted.append({key: item.get(key) for key in ["id", "method", "path"] if item.get(key)})
        else:
            compacted.append(item)
    return compacted


def _compact_nlp_step(step: dict[str, Any], policy: TokenReductionPolicy, path: str, fields: list[str]) -> None:
    decomposition = step.get("decomposition")
    if isinstance(decomposition, dict):
        compacted = {
            "expected_answer_shape": decomposition.get("expected_answer_shape"),
            "sub_question_count": len(decomposition.get("sub_questions") or []),
        }
        compacted = {key: value for key, value in compacted.items() if value not in (None, "", [], {})}
        _replace_if_changed(step, "decomposition", compacted, f"{path}.decomposition", fields)

    relevance = step.get("relevance")
    if isinstance(relevance, dict):
        compacted_relevance = {
            key: _limit_list(value, policy.max_list_items)
            for key, value in relevance.items()
            if value not in (None, "", [], {})
        }
        _replace_if_changed(step, "relevance", compacted_relevance, f"{path}.relevance", fields)

    tokens = step.get("tokens")
    if isinstance(tokens, dict):
        compacted_tokens = {
            key: _limit_list(value, policy.max_list_items)
            for key, value in tokens.items()
            if value not in (None, "", [], {})
        }
        _replace_if_changed(step, "tokens", compacted_tokens, f"{path}.tokens", fields)

    value_retrieval = step.get("value_retrieval")
    if isinstance(value_retrieval, dict):
        compacted_vr: dict[str, Any] = {}
        for key in ["match_count", "budget_exceeded", "retrieval_ms"]:
            if key in value_retrieval:
                compacted_vr[key] = value_retrieval.get(key)
        matches = value_retrieval.get("matches")
        if isinstance(matches, list):
            compacted_vr["matches"] = [_compact_value_match(match) for match in matches[:1] if isinstance(match, dict)]
        _replace_if_changed(step, "value_retrieval", compacted_vr, f"{path}.value_retrieval", fields)


def _compact_value_match(match: dict[str, Any]) -> dict[str, Any]:
    keep = [
        "kind",
        "mention",
        "matched_table",
        "matched_column",
        "matched_value",
        "match_type",
        "confidence",
        "used_for",
    ]
    return {key: summarize_reducible_text(match.get(key), 96) for key in keep if match.get(key) not in (None, "", [], {})}


def _compact_plan_steps(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    compacted = []
    for item in value:
        if not isinstance(item, dict):
            compacted.append(item)
            continue
        step = {key: item.get(key) for key in ["action", "family", "method", "url", "params"] if item.get(key) not in (None, "", [], {})}
        if item.get("sql"):
            step["sql_recorded_in_sql_call"] = True
        if item.get("warnings"):
            step["warnings"] = _dedupe_short_list(item.get("warnings"), DEFAULT_TOKEN_REDUCTION_POLICY.max_list_items)
        compacted.append(step)
    return compacted


def _serialized_official_estimated_tokens(trajectory: dict[str, Any]) -> int:
    canonical_trajectory = json.loads(json.dumps(trajectory, sort_keys=True, default=str))
    return official_estimated_tokens(canonical_trajectory)


def _limit_list(value: Any, limit: int) -> Any:
    return value[:limit] if isinstance(value, list) and len(value) > limit else value


def _dedupe_short_list(value: Any, limit: int) -> Any:
    if not isinstance(value, list):
        return value
    seen: set[str] = set()
    result = []
    for item in value:
        marker = str(item)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(summarize_reducible_text(item, 120))
        if len(result) >= limit:
            break
    return result


def _compact_validation(value: Any, policy: TokenReductionPolicy, path: str, fields: list[str]) -> None:
    if not isinstance(value, dict):
        return
    for key in ["warnings", "errors"]:
        new_value = _dedupe_short_list(value.get(key), policy.max_list_items)
        if new_value != value.get(key):
            value[key] = new_value
            fields.append(f"{path}.{key}")


def _compact_tool_result(value: Any, policy: TokenReductionPolicy, path: str, fields: list[str]) -> None:
    if not isinstance(value, dict):
        return
    if "rows" in value:
        new_rows = compact_preview_rows(value.get("rows"), policy.max_preview_rows, policy.max_cell_chars)
        if new_rows != value.get("rows"):
            value["rows"] = new_rows
            fields.append(f"{path}.rows")
    if "result_preview" in value:
        new_preview = _compact_generic(value.get("result_preview"), policy, f"{path}.result_preview", fields)
        if new_preview != value.get("result_preview"):
            value["result_preview"] = new_preview
            fields.append(f"{path}.result_preview")
    for key in ["message", "detail", "description", "preview"]:
        if key in value:
            new_value = summarize_reducible_text(value.get(key), policy.max_text_chars)
            if new_value != value.get(key):
                value[key] = new_value
                fields.append(f"{path}.{key}")


def _compact_generic(value: Any, policy: TokenReductionPolicy, path: str, fields: list[str]) -> Any:
    if isinstance(value, str):
        return summarize_reducible_text(value, policy.max_text_chars)
    if isinstance(value, list):
        compacted = [_compact_generic(item, policy, f"{path}[]", fields) for item in value[: policy.max_list_items]]
        if len(value) > policy.max_list_items:
            fields.append(path)
        return compacted
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {"rows", "items"}:
                new_child = compact_preview_rows(child, policy.max_preview_rows, policy.max_cell_chars)
            else:
                new_child = _compact_generic(child, policy, child_path, fields)
            if new_child != child:
                fields.append(child_path)
            compacted[key] = new_child
        return compacted
    return value


def _compact_row(row: Any, max_cell_chars: int) -> Any:
    if isinstance(row, dict):
        return {key: summarize_reducible_text(value, max_cell_chars) for key, value in row.items()}
    if isinstance(row, list):
        return [summarize_reducible_text(value, max_cell_chars) for value in row]
    return summarize_reducible_text(row, max_cell_chars)


def _replace_if_changed(target: dict[str, Any], key: str, value: Any, path: str, fields: list[str]) -> None:
    if value != target.get(key):
        target[key] = value
        fields.append(path)
