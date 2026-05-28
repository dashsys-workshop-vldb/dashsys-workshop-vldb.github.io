from __future__ import annotations

from dashagent.answer_slots import AnswerSlots
from dashagent.broad_question_classifier import classify_broad_question


def _slots(query: str, **kwargs) -> AnswerSlots:
    defaults = {"query": query, "answer_family": "unit"}
    defaults.update(kwargs)
    return AnswerSlots(**defaults)


def test_conceptual_broad_schema_question_routes_to_concept() -> None:
    prompt = "What is a schema?"

    decision = classify_broad_question(prompt, slots=_slots(prompt))

    assert decision.broad_question_type == "CONCEPTUAL_BROAD"
    assert decision.confidence == "HIGH"
    assert decision.concept_signal is True
    assert decision.data_signal is False


def test_broad_schema_count_is_data_broad() -> None:
    prompt = "How many schemas do I have?"

    decision = classify_broad_question(prompt, slots=_slots(prompt, counts=[74]))

    assert decision.broad_question_type == "DATA_BROAD"
    assert decision.data_signal is True
    assert "BROAD_DATA_EVIDENCE_REQUIRED" in decision.reason_codes


def test_show_recent_dataset_changes_is_data_broad_list() -> None:
    prompt = "Show recent dataset changes."

    decision = classify_broad_question(prompt, slots=_slots(prompt, entity_names=["Dataset A"]))

    assert decision.broad_question_type == "DATA_BROAD"
    assert decision.data_signal is True


def test_explain_and_show_prompt_is_mixed_broad() -> None:
    prompt = "Explain what inactive journey means and show inactive journeys."

    decision = classify_broad_question(prompt, slots=_slots(prompt, entity_names=["Birthday Message"]))

    assert decision.broad_question_type == "MIXED_BROAD"
    assert decision.concept_signal is True
    assert decision.data_signal is True
    assert decision.mixed_signal is True


def test_ambiguous_prompt_with_concrete_data_signal_forces_data_broad() -> None:
    prompt = "Recent schemas?"

    decision = classify_broad_question(prompt, slots=_slots(prompt, entity_names=["Schema A"]))

    assert decision.broad_question_type == "DATA_BROAD"
    assert "AMBIGUOUS_DATA_SIGNAL_FORCE_DATA" in decision.reason_codes


def test_classifier_context_excludes_benchmark_metadata() -> None:
    prompt = "How many schemas do I have?"

    decision = classify_broad_question(prompt, slots=_slots(prompt, counts=[74]))

    payload = decision.to_dict()
    forbidden = ("gold", "category", "tags", "oracle", "expected_trace", "query_id")
    assert not any(token in str(payload).lower() for token in forbidden)
