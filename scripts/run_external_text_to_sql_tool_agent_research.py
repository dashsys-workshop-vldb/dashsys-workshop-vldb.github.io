#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from scripts.robustness_improvement_common import now_iso, write_report


REPORT_STEM = "external_text_to_sql_tool_agent_research"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_external_text_to_sql_tool_agent_research(config)
    print(json.dumps({"report": REPORT_STEM, "ideas": len(report["ideas"])}, indent=2))
    return 0


def run_external_text_to_sql_tool_agent_research(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    ideas = [
        {
            "source": "Context7 /websites/sqlglot",
            "source_url": "https://sqlglot.com/sqlglot/optimizer/qualify.html",
            "idea": "Use SQLGlot parse, normalization, and table/column qualification as a deterministic validation and SQL-shape comparison layer.",
            "relevance_to_dashsys": "High: DASHSys already uses read-only SQL validation; AST shape checks help detect unsafe or unstable candidate SQL without executing broad speculative queries.",
            "implementation_risk": "low",
            "improves_generalization": True,
            "improves_robustness": True,
            "affects_efficiency": "neutral_to_positive",
            "safe_to_implement_now": False,
            "future_candidate": True,
            "decision": "Keep as candidate for schema-aware/no-template SQL ranking, not a runtime promotion in this pass.",
        },
        {
            "source": "Context7 /websites/vanna_ai",
            "source_url": "https://vanna.ai/docs/placeholder/audit-logging",
            "idea": "Maintain audit logs for tool invocations and results while sanitizing tool parameters and avoiding full sensitive response logging.",
            "relevance_to_dashsys": "High: DASHSys trajectory/reporting can use compact audited tool summaries rather than repeated raw payload context.",
            "implementation_risk": "medium",
            "improves_generalization": False,
            "improves_robustness": True,
            "affects_efficiency": "positive_if_payloads_are_compacted",
            "safe_to_implement_now": False,
            "future_candidate": True,
            "decision": "Use only as design guidance for live API efficiency compression; no dependency or copied implementation.",
        },
        {
            "source": "Context7 /websites/vanna_ai",
            "source_url": "https://vanna.ai/docs/placeholder/llm-context-enhancers",
            "idea": "Context/RAG enhancers should separate successful tool-use examples from failed attempts and keep them bounded.",
            "relevance_to_dashsys": "Medium: generated prompts and controller traces can mine failures, but generated labels must remain diagnostic-only.",
            "implementation_risk": "medium",
            "improves_generalization": True,
            "improves_robustness": True,
            "affects_efficiency": "risk_of_token_growth",
            "safe_to_implement_now": False,
            "future_candidate": True,
            "decision": "Do not add RAG memory; use failure clusters only for offline diagnostics.",
        },
        {
            "source": "Context7 /defog-ai/sqlcoder",
            "source_url": "https://context7.com/defog-ai/sqlcoder/llms.txt",
            "idea": "LLM SQL generation should be treated as candidate generation from schema metadata, then validated before execution.",
            "relevance_to_dashsys": "Medium: aligns with shadow-only schema-aware/LLM SQL candidate policy.",
            "implementation_risk": "high",
            "improves_generalization": True,
            "improves_robustness": "only_with_strict_validation",
            "affects_efficiency": "negative_unless_rarely_activated",
            "safe_to_implement_now": False,
            "future_candidate": True,
            "decision": "Keep LLM SQL candidate generation shadow-only; no promotion without multi-backend and no-LLM gates.",
        },
    ]
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "classification": "diagnostic_only",
        "runtime_change_applied": False,
        "dependencies_added": [],
        "methodology": "Context7 library/doc scan for SQLGlot, Vanna, and SQLCoder patterns; summarized as constraints-mapped design guidance only.",
        "ideas": ideas,
        "safe_now_count": sum(1 for idea in ideas if idea.get("safe_to_implement_now")),
        "future_candidate_count": sum(1 for idea in ideas if idea.get("future_candidate")),
        "recommendation": "Use external patterns as audit and candidate-ranking guidance only; do not add dependencies or promote LLM SQL/controller behavior in this pass.",
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# External Text-to-SQL and Tool-Agent Research",
        "",
        "This scan records external patterns that are relevant to DASHSys, but it does not copy code, add dependencies, or promote new runtime behavior.",
        "",
        f"- Recommendation: `{report.get('recommendation')}`",
        "",
        "## Ideas",
        "",
    ]
    for idea in report.get("ideas", []):
        lines.extend(
            [
                f"### {idea.get('source')}",
                "",
                f"- Source URL: {idea.get('source_url')}",
                f"- Idea: {idea.get('idea')}",
                f"- Relevance: {idea.get('relevance_to_dashsys')}",
                f"- Risk: `{idea.get('implementation_risk')}`",
                f"- Safe to implement now: `{idea.get('safe_to_implement_now')}`",
                f"- Decision: {idea.get('decision')}",
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
