from __future__ import annotations

from dashagent.prompt_semantic_ir import extract_objective_prompt_features
from dashagent.semantic_consistency_verifier import verify_semantic_consistency
from dashagent.semantic_intent_classifier import SemanticIntentDecision
from dashagent.semantic_parse import SemanticParse
from dashagent.semantic_parser import parse_prompt_semantics
from dashagent.semantic_route_decision_ladder import run_semantic_route_decision_ladder
from dashagent.progressive_evidence_policy import decide_progressive_evidence_entry


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


def test_progressive_policy_allows_only_safe_conceptual_no_tool_exit() -> None:
    prompt = "List three reasons why schemas matter."
    features = extract_objective_prompt_features(prompt)
    parsed = parse_prompt_semantics(prompt, features, use_llm=False)
    decision = _decision(True, conf=0.92)
    consistency = verify_semantic_consistency(features, parsed, decision)

    progressive = decide_progressive_evidence_entry(
        features=features,
        semantic_parse=parsed,
        semantic_decision=decision,
        semantic_consistency=consistency,
        no_tool_safety={"allow_no_tool": True, "block": []},
    )

    assert progressive.entry_action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}
    assert progressive.allowed_early_exit is True
    assert progressive.requires_evidence_pipeline is False
    assert "SAFE_CONCEPTUAL_NO_TOOL" in progressive.reason_codes


def test_progressive_policy_forces_supported_data_prompts_to_evidence_pipeline() -> None:
    prompts = [
        "Show inactive journeys.",
        "List current schemas in the sandbox.",
        "How many datasets are in the local snapshot?",
        "Explain merge policy and list current merge policies.",
    ]
    for prompt in prompts:
        features = extract_objective_prompt_features(prompt)
        parsed = parse_prompt_semantics(prompt, features, use_llm=False)
        decision = _decision(True, conf=0.95)
        consistency = verify_semantic_consistency(features, parsed, decision)

        progressive = decide_progressive_evidence_entry(
            features=features,
            semantic_parse=parsed,
            semantic_decision=decision,
            semantic_consistency=consistency,
            no_tool_safety={"allow_no_tool": False, "block": consistency.block_codes},
        )

        assert progressive.entry_action == "EVIDENCE_PIPELINE"
        assert progressive.allowed_early_exit is False
        assert progressive.requires_evidence_pipeline is True
        assert progressive.risk_codes


def test_progressive_policy_tightens_safe_api_probe() -> None:
    merge_prompt = "List current merge policies from the API."
    merge_features = extract_objective_prompt_features(merge_prompt)
    merge_parse = parse_prompt_semantics(merge_prompt, merge_features, use_llm=False)
    merge_decision = _decision(False, need="API", conf=0.9)
    merge_consistency = verify_semantic_consistency(merge_features, merge_parse, merge_decision)

    merge_progressive = decide_progressive_evidence_entry(
        features=merge_features,
        semantic_parse=merge_parse,
        semantic_decision=merge_decision,
        semantic_consistency=merge_consistency,
        no_tool_safety={"allow_no_tool": False, "clear_safe_api_family": True},
        safe_api_probe={"endpoint_id": "merge_policies", "method": "GET", "path": "/data/core/ups/config/mergePolicies", "unresolved_path_params": False},
    )

    assert merge_progressive.entry_action == "SAFE_API_PROBE"
    assert merge_progressive.allowed_early_exit is True

    ambiguous_prompt = "List current schemas and datasets in the sandbox."
    ambiguous_features = extract_objective_prompt_features(ambiguous_prompt)
    ambiguous_parse = parse_prompt_semantics(ambiguous_prompt, ambiguous_features, use_llm=False)
    ambiguous_decision = _decision(False, need="SQL_API", conf=0.78)
    ambiguous_consistency = verify_semantic_consistency(ambiguous_features, ambiguous_parse, ambiguous_decision)

    ambiguous_progressive = decide_progressive_evidence_entry(
        features=ambiguous_features,
        semantic_parse=ambiguous_parse,
        semantic_decision=ambiguous_decision,
        semantic_consistency=ambiguous_consistency,
        no_tool_safety={"allow_no_tool": False, "clear_safe_api_family": False},
        safe_api_probe={"endpoint_id": "schema_registry_schemas", "method": "GET", "path": "/data/foundation/schemaregistry/tenant/schemas", "unresolved_path_params": False},
    )

    assert ambiguous_progressive.entry_action == "EVIDENCE_PIPELINE"
    assert ambiguous_progressive.allowed_early_exit is False
    assert "API_FAMILY_NOT_UNIQUE" in ambiguous_progressive.risk_codes or "API_FAMILY_CONFIDENCE_NOT_HIGH" in ambiguous_progressive.risk_codes


def test_semantic_ladder_reports_progressive_evidence_policy() -> None:
    ladder = run_semantic_route_decision_ladder("Show inactive journeys.", shadow_only=False)

    assert ladder.action == "EVIDENCE_PIPELINE"
    progressive = ladder.checkpoints["checkpoint_progressive_evidence_policy"]
    assert progressive["entry_action"] == "EVIDENCE_PIPELINE"
    assert progressive["requires_evidence_pipeline"] is True


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
