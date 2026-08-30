from __future__ import annotations

from dataclasses import replace

from dashagent.executor import AgentExecutor


def test_ranking_report_only_does_not_change_sql_first_execution(tiny_project):
    baseline_cfg = replace(
        tiny_project,
        outputs_dir=tiny_project.outputs_dir / "baseline",
        enable_hybrid_candidate_scoring=False,
        enable_endpoint_family_ranking=False,
        enable_structural_schema_preservation=False,
        enable_value_to_api_ranking=False,
        enable_gated_risk_cluster_repair=False,
        enable_gated_risk_cluster_repair_execution=False,
    )
    ranking_cfg = replace(
        tiny_project,
        outputs_dir=tiny_project.outputs_dir / "ranking",
        enable_hybrid_candidate_scoring=True,
        enable_endpoint_family_ranking=True,
        enable_structural_schema_preservation=True,
        enable_value_to_api_ranking=True,
        enable_gated_risk_cluster_repair=True,
        enable_gated_risk_cluster_repair_execution=False,
    )
    query = "How many campaigns are there?"
    baseline = AgentExecutor(baseline_cfg).run(query, strategy="SQL_FIRST_API_VERIFY", query_id="same")
    ranking = AgentExecutor(ranking_cfg).run(query, strategy="SQL_FIRST_API_VERIFY", query_id="same")

    assert _executed_sql(baseline["trajectory"]) == _executed_sql(ranking["trajectory"])
    assert _executed_api_endpoints(baseline["trajectory"]) == _executed_api_endpoints(ranking["trajectory"])
    assert len(baseline["tool_results"]) == len(ranking["tool_results"])
    assert baseline["final_answer"] == ranking["final_answer"]
    assert baseline["trajectory"].keys() == ranking["trajectory"].keys()
    assert baseline["metadata"].keys() == ranking["metadata"].keys()


def _executed_sql(trajectory: dict) -> list[str]:
    return [step.get("sql") for step in trajectory.get("steps", []) if step.get("kind") == "sql_call"]


def _executed_api_endpoints(trajectory: dict) -> list[str]:
    endpoints = []
    for step in trajectory.get("steps", []):
        if step.get("kind") == "api_call":
            endpoints.append(f"{step.get('method')} {step.get('url')}")
    return endpoints
