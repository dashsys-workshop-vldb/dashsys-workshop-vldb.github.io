from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .pioneer_model_sweep import GPT4_FAMILY_EXCLUDED_MODELS, is_gpt4_family_model
from .trajectory import redact_secrets


_SKIP_GENERATIVE_RE = re.compile(
    r"(embedding|embed|rerank|guard|guardrail|moderation|classifier|classification|ner|encoder|vision|image|tts|speech|whisper)",
    re.IGNORECASE,
)

_FAMILY_PRIORITY = {
    "qwen": 0,
    "claude": 1,
    "deepseek": 2,
    "llama": 3,
    "mistral": 4,
    "gemma": 5,
    "minimax": 6,
    "kimi": 7,
    "glm": 8,
    "mimo": 9,
    "gpt_oss": 10,
    "other": 99,
}


def build_non_gpt_model_candidates(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a catalog-confirmed non-GPT-4 candidate list without probing providers."""
    excluded_models = _explicit_gpt4_exclusions()
    skipped_models: list[dict[str, Any]] = []
    candidates_by_id: dict[str, dict[str, Any]] = {}

    for record in records:
        display_name = _display_name(record)
        model_id = str(record.get("model_id") or record.get("id") or "").strip()
        if not model_id:
            continue
        if is_gpt4_family_model(display_name, model_id):
            excluded_models.append(
                {
                    "display_name": display_name or model_id,
                    "model_id": model_id,
                    "reason": "excluded_gpt4_family_or_unavailable",
                }
            )
            continue
        suitability = _candidate_suitability(record)
        if not suitability["suitable"]:
            skipped_models.append(
                {
                    "display_name": display_name or model_id,
                    "model_id": model_id,
                    "family": classify_model_family(display_name, model_id),
                    "reason": suitability["reason"],
                }
            )
            continue
        family = classify_model_family(display_name, model_id)
        candidate = {
            "display_name": _canonical_display_name(display_name, model_id),
            "model_id": model_id,
            "family": family,
            "callable": None,
            "catalog_inference_capable": True,
            "source": record.get("source"),
            "supports_inference": record.get("supports_inference"),
            "task_type": record.get("task_type"),
            "availability": None,
            "smoke_status": "not_run",
            "benchmark_status": "not_run",
        }
        existing = candidates_by_id.get(model_id)
        if existing is None or _record_rank(record) < _record_rank(existing):
            candidates_by_id[model_id] = candidate

    candidate_models = sorted(
        candidates_by_id.values(),
        key=lambda row: (_FAMILY_PRIORITY.get(str(row.get("family")), 99), _sort_name(str(row.get("display_name") or ""))),
    )
    return redact_secrets(
        {
            "purpose": "Catalog-confirmed non-GPT-4 Pioneer benchmark candidates for V2.",
            "selection_rules": {
                "exclude_gpt4_family": True,
                "qwen_first": True,
                "skip_non_generative_or_non_inference_models": True,
                "display_name_and_model_id_kept_separate": True,
            },
            "excluded_models": _dedupe_rows(excluded_models),
            "candidate_models": candidate_models,
            "skipped_models": _dedupe_rows(skipped_models),
        }
    )


def apply_run_results_to_candidates(candidate_payload: dict[str, Any], model_results: list[dict[str, Any]]) -> dict[str, Any]:
    by_model_id = {str(row.get("pioneer_model_id") or row.get("model_id") or ""): row for row in model_results}
    by_display = {str(row.get("pioneer_model") or row.get("model") or ""): row for row in model_results}
    updated = dict(candidate_payload)
    candidates: list[dict[str, Any]] = []
    for candidate in candidate_payload.get("candidate_models") or []:
        row = dict(candidate)
        result = by_model_id.get(str(row.get("model_id") or "")) or by_display.get(str(row.get("display_name") or ""))
        if result:
            availability = result.get("availability") or {}
            metrics = result.get("metrics") or {}
            row["callable"] = bool(availability.get("available"))
            row["availability"] = availability
            row["smoke_status"] = "passed" if bool(metrics.get("focused_smoke_pass")) else "failed"
            row["benchmark_status"] = result.get("benchmark_status") or ("completed" if result.get("commands") else "not_run")
        candidates.append(row)
    updated["candidate_models"] = candidates
    return redact_secrets(updated)


def write_non_gpt_candidate_reports(
    report_dir: Path,
    candidate_payload: dict[str, Any],
    *,
    mirror_path: Path | None = None,
) -> dict[str, str]:
    report_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = report_dir / "non_gpt_model_candidates.json"
    candidate_path.write_text(json.dumps(redact_secrets(candidate_payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    paths = {"candidate_json": str(candidate_path)}
    if mirror_path is not None:
        mirror_path.parent.mkdir(parents=True, exist_ok=True)
        mirror_path.write_text(json.dumps(redact_secrets(candidate_payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
        paths["v2_final_benchmark_candidate_json"] = str(mirror_path)
    return paths


def candidate_model_names(candidate_payload: dict[str, Any]) -> list[str]:
    return [str(row["display_name"]) for row in candidate_payload.get("candidate_models") or [] if row.get("display_name")]


def candidate_model_id_map(candidate_payload: dict[str, Any]) -> dict[str, str]:
    return {
        str(row["display_name"]): str(row["model_id"])
        for row in candidate_payload.get("candidate_models") or []
        if row.get("display_name") and row.get("model_id")
    }


def classify_model_family(display_name: str | None, model_id: str | None = None) -> str:
    text = f"{display_name or ''} {model_id or ''}".lower()
    if "qwen" in text:
        return "qwen"
    if "claude" in text:
        return "claude"
    if "deepseek" in text:
        return "deepseek"
    if "llama" in text:
        return "llama"
    if "mistral" in text or "mixtral" in text:
        return "mistral"
    if "gemma" in text:
        return "gemma"
    if "minimax" in text or "mini max" in text:
        return "minimax"
    if "kimi" in text or "moonshot" in text:
        return "kimi"
    if "glm" in text or "zai-org" in text:
        return "glm"
    if "mimo" in text:
        return "mimo"
    if "gpt-oss" in text or "gpt oss" in text:
        return "gpt_oss"
    return "other"


def _explicit_gpt4_exclusions() -> list[dict[str, Any]]:
    return [
        {"display_name": model, "model_id": None, "reason": "excluded_gpt4_family_or_unavailable"}
        for model in sorted(GPT4_FAMILY_EXCLUDED_MODELS)
    ]


def _candidate_suitability(record: dict[str, Any]) -> dict[str, Any]:
    display_name = _display_name(record)
    model_id = str(record.get("model_id") or record.get("id") or "")
    text = f"{display_name} {model_id}"
    if _SKIP_GENERATIVE_RE.search(text):
        return {"suitable": False, "reason": "non_generative_or_guardrail_model"}
    task_type = record.get("task_type")
    if task_type not in (None, "", "decoder"):
        return {"suitable": False, "reason": f"unsupported_task_type:{task_type}"}
    supports = record.get("supports_inference")
    source = str(record.get("source") or "")
    if supports is not True and not source.startswith("openai_models"):
        return {"suitable": False, "reason": "not_catalog_confirmed_inference"}
    return {"suitable": True, "reason": "catalog_inference_decoder_or_openai_model"}


def _record_rank(record: dict[str, Any]) -> int:
    source = str(record.get("source") or "")
    if source == "native_decoder":
        return 0
    if source == "native_inference":
        return 1
    if source.startswith("openai_models"):
        return 2
    return 3


def _display_name(record: dict[str, Any]) -> str:
    return str(record.get("display_name") or record.get("name") or record.get("id") or record.get("model_id") or "").strip()


def _canonical_display_name(display_name: str, model_id: str) -> str:
    text = display_name.strip() or model_id
    replacements = {
        "Qwen3 4B Instruct": "Qwen3 4B Instruct 2507",
        "Mistral Nemo": "Mistral Nemo Instruct 2407",
        "Gemma 4 E4B IT": "Gemma 4 E4B It",
        "Gemma 4 31B IT": "Gemma 4 31B It",
    }
    return replacements.get(text, text)


def _sort_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("display_name") or ""), str(row.get("model_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped
