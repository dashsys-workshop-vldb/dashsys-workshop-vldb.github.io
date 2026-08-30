from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PROMOTION_ELIGIBLE_SOURCES = {"organizer_strict", "hidden_style"}
ORGANIZER_EQUIVALENT_SOURCES = {"organizer_strict"}
VALID_SCORE_SOURCES = {
    "organizer_strict",
    "internal_500_heuristic",
    "internal_500_organizer_style",
    "simulated_trace",
    "hidden_style",
}


@dataclass(frozen=True)
class ScoreProvenance:
    score_source: str
    real_agent_execution: bool
    synthetic_trace: bool
    organizer_equivalent: bool
    runtime_gold_visible: bool
    promotion_eligible: bool
    grading_type: str
    evaluator_script: str
    dataset_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_score_provenance(
    *,
    score_source: str,
    real_agent_execution: bool,
    synthetic_trace: bool,
    grading_type: str,
    evaluator_script: str,
    dataset_path: str,
    runtime_gold_visible: bool = False,
    organizer_equivalent: bool | None = None,
    promotion_eligible: bool | None = None,
) -> ScoreProvenance:
    normalized_source = str(score_source or "unknown")
    if normalized_source not in VALID_SCORE_SOURCES:
        normalized_source = "simulated_trace" if synthetic_trace else normalized_source
    is_organizer_equivalent = (
        normalized_source in ORGANIZER_EQUIVALENT_SOURCES if organizer_equivalent is None else bool(organizer_equivalent)
    )
    is_promotion_eligible = (
        normalized_source in PROMOTION_ELIGIBLE_SOURCES
        and bool(real_agent_execution)
        and not bool(synthetic_trace)
        and not bool(runtime_gold_visible)
        if promotion_eligible is None
        else bool(promotion_eligible)
    )
    if synthetic_trace or runtime_gold_visible:
        is_promotion_eligible = False
    if normalized_source in {"internal_500_heuristic", "internal_500_organizer_style", "simulated_trace"}:
        is_organizer_equivalent = False
        if normalized_source != "hidden_style":
            is_promotion_eligible = False
    return ScoreProvenance(
        score_source=normalized_source,
        real_agent_execution=bool(real_agent_execution),
        synthetic_trace=bool(synthetic_trace),
        organizer_equivalent=is_organizer_equivalent,
        runtime_gold_visible=bool(runtime_gold_visible),
        promotion_eligible=is_promotion_eligible,
        grading_type=str(grading_type or "unknown"),
        evaluator_script=str(evaluator_script or ""),
        dataset_path=str(dataset_path or ""),
    )


def infer_score_provenance(report: dict[str, Any], *, path: str = "") -> ScoreProvenance:
    text = f"{path} {report.get('score_source', '')} {report.get('grading_type', '')}".lower()
    if report.get("simulated_trace_only") or "simulated" in text:
        source = "simulated_trace"
    elif "hidden" in text:
        source = "hidden_style"
    elif "500" in text and "organizer" in text:
        source = "internal_500_organizer_style"
    elif "500" in text:
        source = "internal_500_heuristic"
    else:
        source = "organizer_strict"
    return build_score_provenance(
        score_source=source,
        real_agent_execution=bool(report.get("real_agent_execution", source in {"organizer_strict", "hidden_style"})),
        synthetic_trace=bool(report.get("synthetic_trace", report.get("simulated_trace_only", False))),
        runtime_gold_visible=bool(report.get("runtime_gold_visible", False)),
        grading_type=str(report.get("grading_type") or ("hidden_style" if source == "hidden_style" else "organizer_style_strict")),
        evaluator_script=str(report.get("evaluator_script") or _default_evaluator(source)),
        dataset_path=str(report.get("dataset_path") or report.get("suite") or _default_dataset(source)),
    )


def _default_evaluator(source: str) -> str:
    if source == "hidden_style":
        return "scripts/run_hidden_style_eval.py"
    if source in {"internal_500_heuristic", "simulated_trace"}:
        return "scripts/run_dashagent_500_prompt_suite_eval.py"
    return "scripts/run_dev_eval.py"


def _default_dataset(source: str) -> str:
    if source in {"internal_500_heuristic", "simulated_trace"}:
        return "data/benchmarks/dashagent_500_prompt_suite.jsonl"
    if source == "internal_500_organizer_style":
        return "data/benchmarks/dashagent_500_organizer_style.json"
    if source == "hidden_style":
        return "generated_hidden_style_cases"
    return "data/data.json"
