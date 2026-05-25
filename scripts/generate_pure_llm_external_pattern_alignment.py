#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config

REPORT_STEM = "pure_llm_external_pattern_alignment"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_pure_llm_external_pattern_alignment(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "patterns": len(payload["patterns"])}, indent=2))
    return 0


def generate_pure_llm_external_pattern_alignment(config: Config | None = None) -> dict:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    patterns = [
        {
            "pattern": "LangChain-style controlled agent workflow",
            "implemented": True,
            "implemented_module": "dashagent/pure_llm_tool_agent.py",
            "safety_guard": "explicit plan, validated tool steps, trace report; no packaged runtime promotion",
            "remaining_gap": "not a full framework and no autonomous multi-step planner promotion",
        },
        {
            "pattern": "Vanna-style schema retrieval/context",
            "implemented": True,
            "implemented_module": "dashagent/llm_sql_context_builder.py",
            "safety_guard": "known SchemaIndex tables/columns only; no gold answers or query IDs",
            "remaining_gap": "no learned documentation index or user feedback loop",
        },
        {
            "pattern": "SQLCoder-style schema-aware SQL prompt",
            "implemented": True,
            "implemented_module": "dashagent/llm_tool_agent_prompts.py",
            "safety_guard": "JSON-only candidate schema and existing SQLValidator/SQLGlot validation",
            "remaining_gap": "model quality still controls candidate SQL quality",
        },
        {
            "pattern": "SQLFixAgent-style validation/repair loop",
            "implemented": True,
            "implemented_module": "dashagent/llm_sql_repair_loop.py",
            "safety_guard": "invalid SQL is never executed; max two repair rounds",
            "remaining_gap": "repair success depends on model following validator feedback",
        },
        {
            "pattern": "SQLGlot/SQLValidator hard validation",
            "implemented": True,
            "implemented_module": "dashagent/validators.py",
            "safety_guard": "read-only, known table/column, AST destructive SQL checks before execution",
            "remaining_gap": "semantic wrong-table/wrong-filter errors need scoring feedback",
        },
    ]
    payload = {
        "report_type": REPORT_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "promotion_allowed": False,
        "ctx7_docs_used": [{"library_id": "/tobymao/sqlglot", "topic": "parse AST validation safe SQL analysis"}],
        "patterns": patterns,
    }
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = ["# Pure LLM External Pattern Alignment", "", "Diagnostic-only comparison; no external framework is imported."]
    for item in patterns:
        lines.append(f"- `{item['pattern']}`: implemented `{item['implemented']}` in `{item['implemented_module']}`; guard: {item['safety_guard']}")
    (reports_dir / f"{REPORT_STEM}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
