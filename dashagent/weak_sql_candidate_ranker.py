from __future__ import annotations

from typing import Any

from .trajectory import redact_secrets


def rank_sql_candidates(prompt: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    ranking = []
    features: dict[str, dict[str, Any]] = {}
    rejection_reasons: dict[str, list[str]] = {}
    for index, candidate in enumerate(candidates):
        candidate_id = str(candidate.get("candidate_id") or candidate.get("id") or f"c{index + 1}")
        unit = candidate.get("sql_unit_tests") if isinstance(candidate.get("sql_unit_tests"), dict) else {}
        validation = candidate.get("validation") if isinstance(candidate.get("validation"), dict) else {}
        probe = candidate.get("execution_probe") if isinstance(candidate.get("execution_probe"), dict) else {}
        sql = str(candidate.get("sql") or "")
        reasons: list[str] = []
        unit_passed = bool(unit.get("passed"))
        validation_ok = validation.get("ok") is not False
        probe_ok = probe.get("probe_ok") is not False
        compactness = max(0.0, 1.0 - len(sql) / 1200.0)
        semantic_score = float(unit.get("semantic_score") or (1.0 if unit_passed else 0.0))
        score = 0.0
        score += 4.0 if unit_passed else -4.0
        score += 3.0 if validation_ok else -5.0
        score += 1.5 if probe_ok else -1.5
        score += semantic_score * 2.0
        score += compactness
        if not sql:
            reasons.append("no_executable_sql")
            score -= 10.0
        if not unit_passed:
            reasons.append("unit_tests_failed")
        if not validation_ok:
            reasons.append("sql_validation_failed")
        if not probe_ok:
            reasons.append("execution_probe_failed")
        features[candidate_id] = {
            "unit_tests_passed": unit_passed,
            "validation_ok": validation_ok,
            "probe_ok": probe_ok,
            "semantic_score": round(semantic_score, 4),
            "compactness": round(compactness, 4),
            "score": round(score, 4),
        }
        if reasons:
            rejection_reasons[candidate_id] = reasons
        ranking.append({"candidate_id": candidate_id, "score": round(score, 4), "rejected": bool(reasons), "rejection_reasons": reasons})
    ranking.sort(key=lambda item: (-float(item["score"]), item["candidate_id"]))
    selected = next((item["candidate_id"] for item in ranking if not item["rejected"]), ranking[0]["candidate_id"] if ranking else "")
    return redact_secrets({"selected_candidate_id": selected, "ranking": ranking, "ranking_features": features, "rejection_reasons": rejection_reasons})
