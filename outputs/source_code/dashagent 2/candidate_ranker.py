from __future__ import annotations

import re
from typing import Any

from .endpoint_family_ranker import endpoint_family_for_endpoint
from .query_tokens import QueryTokens
from .relevance_scorer import RelevanceItem, split_identifier


FUSION_MODES = {"weighted_score_fusion", "reciprocal_rank_fusion"}


def score_candidate(
    query_tokens: QueryTokens,
    candidate: dict[str, Any],
    value_matches: list[Any] | None = None,
    schema_links: dict[str, Any] | None = None,
    endpoint_family: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = str(candidate.get("name") or candidate.get("id") or "")
    kind = str(candidate.get("kind") or "table")
    words = set(query_tokens.words)
    candidate_words = set(split_identifier(name)) | set(re.findall(r"[a-z0-9]+", str(candidate.get("text") or "").lower()))
    lexical_score = min(1.0, 0.35 * len(words & candidate_words))
    if name.lower().replace("_", " ") in query_tokens.matching_text:
        lexical_score += 0.25
    alias_score = _alias_score(name, candidate, schema_links, words)
    value_match_score = _value_match_score(name, kind, value_matches or [])
    structural_score = 0.5 if candidate.get("structural") else 0.0
    endpoint_family_score = _endpoint_family_component(candidate, endpoint_family or {}) if kind == "api" else 0.0
    base_score = float(candidate.get("base_score") or 0.0)
    final_score = (
        min(base_score, 3.0) * 0.3
        + lexical_score
        + alias_score
        + value_match_score
        + structural_score
        + endpoint_family_score
    )
    return {
        "name": name,
        "kind": kind,
        "lexical_score": round(lexical_score, 4),
        "alias_score": round(alias_score, 4),
        "value_match_score": round(value_match_score, 4),
        "structural_score": round(structural_score, 4),
        "endpoint_family_score": round(endpoint_family_score, 4),
        "base_score": round(base_score, 4),
        "final_score": round(final_score, 4),
        "weighted_score_fusion": round(final_score, 4),
        "score_explanation": _explanation(base_score, lexical_score, alias_score, value_match_score, structural_score, endpoint_family_score),
    }


def rank_candidates(
    query_tokens: QueryTokens,
    candidates: list[dict[str, Any]],
    *,
    value_matches: list[Any] | None = None,
    schema_links: dict[str, Any] | None = None,
    endpoint_family: dict[str, Any] | None = None,
    fusion_mode: str = "weighted_score_fusion",
) -> dict[str, Any]:
    if fusion_mode not in FUSION_MODES:
        raise ValueError(f"Unsupported fusion mode {fusion_mode}")
    scored = [
        {
            **candidate,
            **score_candidate(query_tokens, candidate, value_matches, schema_links, endpoint_family),
        }
        for candidate in candidates
    ]
    component_rankings = _component_rankings(scored)
    rrf_scores = reciprocal_rank_fusion(component_rankings)
    for row in scored:
        row["reciprocal_rank_fusion"] = round(rrf_scores.get(row["name"], 0.0), 6)
    sort_key = "reciprocal_rank_fusion" if fusion_mode == "reciprocal_rank_fusion" else "weighted_score_fusion"
    ranked = sorted(scored, key=lambda row: (-float(row.get(sort_key) or 0.0), row["name"]))
    before = [candidate.get("name") or candidate.get("id") for candidate in candidates]
    after = [row["name"] for row in ranked]
    return {
        "fusion_mode": fusion_mode,
        "ranked_candidates": ranked,
        "rank_before": before,
        "rank_after": after,
        "ranking_changed": before != after[: len(before)],
        "top_candidate_score": ranked[0].get(sort_key) if ranked else 0.0,
        "score_margin": _score_margin(ranked, sort_key),
        "component_rankings": component_rankings,
    }


def reciprocal_rank_fusion(rankings: list[list[str]], *, k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for index, name in enumerate(ranking):
            scores[name] = scores.get(name, 0.0) + 1.0 / (k + index + 1)
    return scores


def relevance_items_to_candidates(items: list[RelevanceItem], *, kind: str) -> list[dict[str, Any]]:
    return [{"name": item.name, "kind": kind, "base_score": item.score, "text": item.reason} for item in items]


def _component_rankings(scored: list[dict[str, Any]]) -> list[list[str]]:
    keys = ["base_score", "lexical_score", "alias_score", "value_match_score", "structural_score", "endpoint_family_score"]
    rankings = []
    for key in keys:
        nonzero = [row for row in scored if float(row.get(key) or 0.0) > 0]
        if nonzero:
            rankings.append([row["name"] for row in sorted(nonzero, key=lambda row: (-float(row.get(key) or 0.0), row["name"]))])
    return rankings


def _alias_score(name: str, candidate: dict[str, Any], schema_links: dict[str, Any] | None, words: set[str]) -> float:
    score = 0.0
    aliases = set(candidate.get("aliases") or [])
    if aliases & words:
        score += 0.8
    for link in (schema_links or {}).get("links", []):
        if link.get("table") == name:
            score += min(0.9, float(link.get("score") or 0.0) * 0.6)
    return min(score, 1.2)


def _value_match_score(name: str, kind: str, value_matches: list[Any]) -> float:
    score = 0.0
    for match in value_matches:
        payload = match.to_dict() if hasattr(match, "to_dict") else dict(match)
        confidence = float(payload.get("confidence") or 0.0)
        if confidence < 0.94:
            continue
        matched_table = str(payload.get("matched_table") or "")
        used_for = str(payload.get("used_for") or "")
        if kind == "table" and matched_table == name:
            score += 0.7 * confidence
        elif kind == "api" and used_for in {"api_param", "answer_grounding"}:
            score += 0.4 * confidence
    return min(score, 1.0)


def _endpoint_family_component(candidate: dict[str, Any], endpoint_family: dict[str, Any]) -> float:
    family = endpoint_family.get("endpoint_family")
    if not family:
        return 0.0
    candidate_family = candidate.get("endpoint_family") or endpoint_family_for_endpoint(str(candidate.get("name") or ""))
    if candidate_family != family:
        return 0.0
    return float(endpoint_family.get("endpoint_family_confidence") or 0.0)


def _score_margin(ranked: list[dict[str, Any]], key: str) -> float:
    if not ranked:
        return 0.0
    top = float(ranked[0].get(key) or 0.0)
    second = float(ranked[1].get(key) or 0.0) if len(ranked) > 1 else 0.0
    return round(max(0.0, top - second), 4)


def _explanation(base: float, lexical: float, alias: float, value: float, structural: float, endpoint: float) -> str:
    return (
        f"base={base:.3f}; lexical={lexical:.3f}; alias={alias:.3f}; "
        f"value={value:.3f}; structural={structural:.3f}; endpoint_family={endpoint:.3f}"
    )
