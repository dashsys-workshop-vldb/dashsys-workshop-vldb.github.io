from __future__ import annotations

from dashagent.answer_slots import AnswerSlots
from dashagent.evidence_grounded_llm_answer_generator import generate_evidence_grounded_llm_answer
from dashagent.llm_client import NoOpLLMClient


class FakeAnswerClient:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def complete(self, messages):
        return self.answer


class GenerateMessagesClient:
    def __init__(self, response) -> None:
        self.response = response

    def generate_messages(self, messages):
        return self.response


class CapturingAnswerClient:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.messages = None

    def generate_messages(self, messages):
        self.messages = messages
        return {"ok": True, "content": self.answer, "finish_reason": "stop"}


class ProviderMessagesClient:
    def __init__(self, provider: str, response) -> None:
        self.provider = provider
        self.response = response

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return self.provider

    def model_name(self) -> str:
        return f"{self.provider}-unit-model"

    def generate_messages(self, messages):
        return self.response


def _slots() -> AnswerSlots:
    return AnswerSlots(
        query="Show schema status",
        answer_family="status",
        entity_names=["Profile Schema"],
        entity_ids=["schema-123"],
        statuses=["active"],
        first_rows=[{"id": "schema-123", "name": "Profile Schema", "status": "active"}],
        evidence_strings={"profile schema", "schema-123", "active"},
    )


def test_llm_answer_generator_accepts_free_wording_when_grounded() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=FakeAnswerClient("Profile Schema is active."),
    )

    assert result.final_answer == "Profile Schema is active."
    assert result.verification.ok is True
    assert result.fallback_used is False


def test_llm_answer_generator_falls_back_when_answer_overreaches() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=FakeAnswerClient("Profile Schema is inactive."),
    )

    assert result.final_answer == "Status: {id=schema-123, name=Profile Schema, status=active}."
    assert result.fallback_used is True


def test_llm_answer_generator_falls_back_when_answer_empty() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=FakeAnswerClient("   "),
    )

    assert result.final_answer == "Status: {id=schema-123, name=Profile Schema, status=active}."
    assert result.fallback_used is True
    assert result.generator_category == "LLM_RAW_RESPONSE_EMPTY"


def test_openai_choices_message_content_response_is_parsed() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=GenerateMessagesClient(
            {
                "ok": True,
                "choices": [
                    {
                        "message": {"content": "Profile Schema is active."},
                        "finish_reason": "stop",
                    }
                ],
            }
        ),
    )

    assert result.final_answer == "Profile Schema is active."
    assert result.generator_category is None
    assert result.debug["extracted_content_length"] > 0
    assert result.debug["finish_reason"] == "stop"


def test_output_text_response_is_parsed() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=GenerateMessagesClient({"ok": True, "output_text": "Profile Schema is active."}),
    )

    assert result.final_answer == "Profile Schema is active."
    assert result.generator_category is None


def test_empty_generate_messages_response_is_classified() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=GenerateMessagesClient({"ok": True, "content": "", "finish_reason": "stop"}),
    )

    assert result.fallback_used is True
    assert result.generator_category == "LLM_RAW_RESPONSE_EMPTY"
    assert result.debug["raw_response_present"] is True
    assert result.debug["extracted_content_length"] == 0


def test_failed_llm_response_without_error_category_is_classified_as_raw_empty_response() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=GenerateMessagesClient({"ok": False, "content": "", "error": "redacted provider error"}),
    )

    assert result.fallback_used is True
    assert result.generator_category == "LLM_RAW_RESPONSE_EMPTY"
    assert result.debug["raw_response_ok"] is False
    assert result.debug["raw_response_error_present"] is True


def test_failed_llm_response_with_auth_category_is_classified_as_backend_auth_failed() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=GenerateMessagesClient(
            {
                "ok": False,
                "content": "",
                "error": "redacted provider error",
                "error_category": "auth_or_401",
            }
        ),
    )

    assert result.fallback_used is True
    assert result.generator_category == "LLM_BACKEND_AUTH_FAILED"
    assert result.generator_error == "LLM_BACKEND_AUTH_FAILED"
    assert result.debug["raw_response_ok"] is False
    assert result.debug["raw_response_error_present"] is True
    assert result.debug["raw_response_error_category"] == "auth_or_401"
    assert "backend_fallback_attempts" not in result.debug


def test_default_backend_auth_failure_falls_back_to_working_sdk_provider(monkeypatch) -> None:
    primary = ProviderMessagesClient(
        "openrouter",
        {
            "ok": False,
            "content": "",
            "error": "redacted provider error",
            "error_category": "auth_or_401",
        },
    )
    fallback = ProviderMessagesClient("openai", {"ok": True, "content": "Profile Schema is active.", "finish_reason": "stop"})

    def fake_get_llm_client(provider=None):
        if provider in (None, "openrouter"):
            return primary
        if provider in {"openai", "openai_compatible"}:
            return fallback
        return NoOpLLMClient(reason="unit backend unavailable")

    monkeypatch.setattr(
        "dashagent.evidence_grounded_llm_answer_generator.get_llm_client",
        fake_get_llm_client,
    )

    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
    )

    assert result.final_answer == "Profile Schema is active."
    assert result.generator_category is None
    assert result.fallback_used is False
    assert result.debug["backend_fallback_used"] is True
    attempts = result.debug["backend_fallback_attempts"]
    assert attempts[0]["category"] == "LLM_BACKEND_AUTH_FAILED"
    assert attempts[1]["llm_client_name"] == "openai"
    assert attempts[1]["content_length"] > 0


def test_llm_answer_prompt_includes_requested_roles_and_exact_fact_payload() -> None:
    client = CapturingAnswerClient("The local snapshot contains 74 schema records.")
    slots = AnswerSlots(
        query="How many schema records are in the local snapshot?",
        answer_family="schema_count",
        counts=[74],
        sql_row_count=74,
        first_rows=[{"count": 74}],
        evidence_strings={"74"},
    )

    result = generate_evidence_grounded_llm_answer(
        slots.query,
        deterministic_answer="Count: 74.",
        slots=slots,
        llm_client=client,
    )

    assert result.final_answer == "The local snapshot contains 74 schema records."
    assert client.messages is not None
    payload = __import__("json").loads(client.messages[1]["content"])
    assert "count" in payload["runtime_requested_roles"]
    assert payload["exact_facts"]["counts"] == ["74"]
    assert payload["exact_facts"]["sql_row_count"] == 74
    assert payload["answer_requirements"][0].startswith("Include all available facts")
    assert payload["fallback_renderer_answer"] == "Count: 74."


def test_malformed_response_is_classified_as_content_extraction_failed() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=GenerateMessagesClient({"ok": True, "choices": "malformed"}),
    )

    assert result.fallback_used is True
    assert result.generator_category == "CONTENT_FIELD_EXTRACTION_FAILED"


def test_llm_answer_generator_reports_unavailable_backend_without_empty_llm_error() -> None:
    result = generate_evidence_grounded_llm_answer(
        "Show schema status",
        deterministic_answer="Status: {id=schema-123, name=Profile Schema, status=active}.",
        slots=_slots(),
        llm_client=NoOpLLMClient(reason="unit backend unavailable"),
    )

    assert result.final_answer == "Status: {id=schema-123, name=Profile Schema, status=active}."
    assert result.llm_backend_used is False
    assert result.generator_error == "unit backend unavailable"
    assert result.generator_category == "LLM_BACKEND_UNAVAILABLE"
