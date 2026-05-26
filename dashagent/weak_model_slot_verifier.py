from __future__ import annotations

from typing import Any

from .nlp_generalization_layer import normalize_prompt_semantics
from .trajectory import redact_secrets


def verify_semantic_slots(prompt: str, slots: dict[str, Any]) -> dict[str, Any]:
    nlp = normalize_prompt_semantics(prompt)
    corrected = dict(slots)
    errors: list[str] = []
    warnings: list[str] = []
    intent = str(slots.get("intent") or "UNKNOWN").upper()
    domain = str(slots.get("domain") or "UNKNOWN").upper()
    evidence_need = str(slots.get("evidence_need") or "unknown").lower()
    if nlp["canonical_intent"] != "UNKNOWN" and intent != nlp["canonical_intent"]:
        warnings.append("intent_adjusted_to_prompt")
        corrected["intent"] = nlp["canonical_intent"]
    if nlp["canonical_domain"] != "UNKNOWN" and domain == "UNKNOWN":
        warnings.append("domain_adjusted_to_prompt")
        corrected["domain"] = nlp["canonical_domain"]
    local_snapshot = nlp["canonical_domain"] != "UNKNOWN" and "api" not in prompt.lower() and "live" not in prompt.lower()
    if local_snapshot and evidence_need == "api_only":
        errors.append("sql_likely_required_api_only")
        corrected["evidence_need"] = "sql_first"
    if intent in {"COUNT", "LIST", "STATUS", "DATE", "DETAIL"} and evidence_need == "unknown":
        errors.append("tool_evidence_required")
        corrected["evidence_need"] = "sql_first" if local_snapshot else "api_first"
    if nlp.get("quoted_entities") and not slots.get("quoted_entities"):
        warnings.append("quoted_entities_added_from_prompt")
        corrected["quoted_entities"] = nlp["quoted_entities"]
    corrected.setdefault("filters", nlp.get("canonical_filters", []))
    return redact_secrets({"ok": not errors, "errors": errors, "warnings": warnings, "corrected_slots": corrected})
