from __future__ import annotations

from dashagent.prompt_semantic_ir import extract_objective_prompt_features
from dashagent.semantic_consistency_verifier import verify_semantic_consistency
from dashagent.semantic_intent_classifier import SemanticIntentDecision
from dashagent.semantic_parse import SemanticParse
from dashagent.semantic_parser import parse_prompt_semantics
from dashagent.semantic_route_decision_ladder import run_semantic_route_decision_ladder


def _decision(no_tool: bool, need: str = "NONE", conf: float = 0.9) -> SemanticIntentDecision:
    return SemanticIntentDecision(
        intent="CONCEPT" if no_tool else "DATA",
        need=need,
        no_tool=no_tool,
        sql=need in {"SQL", "SQL_API"},
        api=need in {"API", "SQL_API"},
        conf=conf,
        codes=["UNIT"],
    )


def test_semantic_parse_allows_list_as_conceptual_format_request() -> None:
    features = extract_objective_prompt_features("List three reasons why schemas matter.")
    parsed = parse_prompt_semantics("List three reasons why schemas matter.", features, use_llm=False)

    assert parsed.operation in {"LIST", "FORMAT_REQUEST"}
    assert parsed.target.grounding == "CONCEPTUAL_OBJECT"
    assert parsed.target.instance_level is False
    assert parsed.evidence_need == "NONE"
    assert parsed.no_tool_safe is True
    assert "FORMAT_REQUEST" in parsed.risk_codes or "conceptual_object_terms" in features.to_dict()

    verified = verify_semantic_consistency(features, parsed, _decision(True))
    assert verified.allow_no_tool is True
    assert verified.ok is True
    assert verified.fallback_action is None


def test_semantic_parse_allows_inactive_journey_definition() -> None:
    prompt = "What does 'inactive journey' mean?"
    features = extract_objective_prompt_features(prompt)
    parsed = parse_prompt_semantics(prompt, features, use_llm=False)

    assert parsed.operation == "DEFINE"
    assert parsed.target.grounding in {"CONCEPTUAL_OBJECT", "META_LANGUAGE"}
    assert parsed.target.instance_level is False
    assert parsed.evidence_need == "NONE"

    verified = verify_semantic_consistency(features, parsed, _decision(True))
    assert verified.allow_no_tool is True
    assert "KEYWORD_ONLY_BLOCK_AVOIDED" in verified.consistency_codes


def test_semantic_parse_allows_meta_language_list_schemas_phrase() -> None:
    prompt = "In the phrase 'list schemas', what does 'list' mean?"
    features = extract_objective_prompt_features(prompt)
    parsed = parse_prompt_semantics(prompt, features, use_llm=False)

    assert parsed.operation in {"DEFINE", "META_LANGUAGE"}
    assert parsed.target.grounding == "META_LANGUAGE"
    assert parsed.evidence_need == "NONE"

    verified = verify_semantic_consistency(features, parsed, _decision(True))
    assert verified.allow_no_tool is True


def test_semantic_parse_blocks_current_schema_retrieval_no_tool() -> None:
    prompt = "List current schemas in the sandbox."
    features = extract_objective_prompt_features(prompt)
    parsed = parse_prompt_semantics(prompt, features, use_llm=False)

    assert parsed.operation == "LIST"
    assert parsed.target.grounding == "SUPPORTED_DATA_OBJECT"
    assert parsed.target.instance_level is True
    assert parsed.evidence_need in {"API", "SQL_API"}

    verified = verify_semantic_consistency(features, parsed, _decision(True))
    assert verified.allow_no_tool is False
    assert "SUPPORTED_DATA_OBJECT" in verified.block_codes
    assert verified.fallback_action in {"EVIDENCE_PIPELINE", "SAFE_API_PROBE"}


def test_semantic_parse_blocks_inactive_journeys_lookup_no_tool() -> None:
    prompt = "Show inactive journeys."
    features = extract_objective_prompt_features(prompt)
    parsed = parse_prompt_semantics(prompt, features, use_llm=False)

    assert parsed.operation in {"LIST", "STATUS"}
    assert parsed.target.grounding == "SUPPORTED_DATA_OBJECT"
    assert parsed.target.instance_level is True
    assert parsed.filters.status == "INACTIVE"

    verified = verify_semantic_consistency(features, parsed, _decision(True))
    assert verified.allow_no_tool is False
    assert "INSTANCE_LEVEL" in verified.block_codes


def test_semantic_parse_blocks_local_dataset_count_no_tool() -> None:
    prompt = "How many datasets are in the local snapshot?"
    features = extract_objective_prompt_features(prompt)
    parsed = parse_prompt_semantics(prompt, features, use_llm=False)

    assert parsed.operation == "COUNT"
    assert parsed.target.grounding == "SUPPORTED_DATA_OBJECT"
    assert parsed.evidence_need == "SQL"

    verified = verify_semantic_consistency(features, parsed, _decision(True))
    assert verified.allow_no_tool is False
    assert "EVIDENCE_NEEDED" in verified.block_codes


def test_semantic_parse_handles_out_of_domain_without_sql_api_route() -> None:
    prompt = "List Adobe stock price trends."
    features = extract_objective_prompt_features(prompt)
    parsed = parse_prompt_semantics(prompt, features, use_llm=False)

    assert parsed.operation in {"LIST", "FORMAT_REQUEST"}
    assert parsed.target.grounding == "OUT_OF_DOMAIN"
    assert parsed.capability.sql_match is False
    assert parsed.capability.api_match is False

    ladder = run_semantic_route_decision_ladder(prompt, shadow_only=False)
    assert ladder.action in {"LLM_SAFE_DIRECT", "LLM_DIRECT"}
    assert ladder.action != "EVIDENCE_PIPELINE"


def test_keyword_decoys_do_not_force_evidence_pipeline() -> None:
    prompts = [
        "Explain why the word list appears in API docs.",
        "Give examples of status fields; do not query the dataset.",
    ]
    for prompt in prompts:
        features = extract_objective_prompt_features(prompt)
        parsed = parse_prompt_semantics(prompt, features, use_llm=False)
        verified = verify_semantic_consistency(features, parsed, _decision(True, conf=0.78))

        assert parsed.target.grounding in {"CONCEPTUAL_OBJECT", "META_LANGUAGE", "OUT_OF_DOMAIN"}
        assert parsed.evidence_need == "NONE"
        assert verified.allow_no_tool is True


def test_semantic_parse_json_round_trip_schema() -> None:
    parsed = parse_prompt_semantics("List three reasons why schemas matter.", use_llm=False)
    payload = parsed.to_dict()
    restored = SemanticParse.from_dict(payload)

    assert restored.to_dict() == payload
    assert set(payload) == {
        "operation",
        "target",
        "filters",
        "requested_fields",
        "capability",
        "evidence_need",
        "no_tool_safe",
        "confidence",
        "supporting_spans",
        "risk_codes",
        "source",
    }
