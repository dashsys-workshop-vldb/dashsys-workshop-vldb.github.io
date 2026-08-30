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
from dashagent.local_knowledge_index import build_local_knowledge_index
from dashagent.report_run import report_metadata


def main() -> int:
    config = Config.from_env(ROOT)
    payload = build_local_knowledge_index_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "local_knowledge_index_report.json"
    md_path = config.outputs_dir / "local_knowledge_index_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "evidence_object_count": payload["summary"]["evidence_object_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_local_knowledge_index_report(config: Config) -> dict[str, Any]:
    index = build_local_knowledge_index(config)
    summary = {
        **index.build_summary,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "gold_used_for_runtime": False,
        "data_json_used_for_runtime": False,
        "local_index_returns_final_answers": False,
    }
    return {
        **report_metadata(config.outputs_dir),
        "mode": "local_knowledge_index_report",
        "diagnostic_only": True,
        "packaged_execution_changed": False,
        "summary": summary,
        "runtime_sources": {
            "parquet_glob": "data/DBSnapshot/*.parquet",
            "parquet_only": True,
            "data_json_used_for_runtime": False,
            "gold_sql_api_answers_used_for_runtime": False,
        },
        "table_summaries": index.table_summaries,
        "evidence_type_counts": index.build_summary.get("evidence_type_counts", {}),
        "sample_evidence_objects": [obj.to_dict() for obj in index.evidence_objects[:25]],
        "rejected_objects": index.rejected_objects,
        "notes": [
            "The local knowledge index is Parquet-derived diagnostic infrastructure only.",
            "Evidence objects are not final answers and are not wired into packaged execution on this branch.",
            "Runtime generation must not read data/data.json gold traces, answers, SQL, or API paths.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Local Knowledge Index Report",
        "",
        "This report describes a Parquet-derived evidence-object index. It does not change packaged execution.",
        "",
        f"- Parquet files scanned: {summary['parquet_files_scanned']}",
        f"- Tables indexed: {summary['tables_indexed']}",
        f"- Evidence objects: {summary['evidence_object_count']}",
        f"- Rejected objects: {summary['rejected_object_count']}",
        f"- Data JSON used for runtime: {summary['data_json_used_for_runtime']}",
        f"- Local index returns final answers: {summary['local_index_returns_final_answers']}",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        "",
        "## Evidence Types",
        "",
    ]
    for evidence_type, count in payload.get("evidence_type_counts", {}).items():
        lines.append(f"- {evidence_type}: {count}")
    lines.extend(["", "## Indexed Tables", ""])
    for table in payload.get("table_summaries", [])[:30]:
        domains = ", ".join(table.get("likely_domains", []))
        high_signal = ", ".join(table.get("high_signal_columns", [])[:8])
        lines.append(
            f"- `{table['table']}`: rows={table['row_count']} columns={table['column_count']} "
            f"domains={domains} high_signal=[{high_signal}]"
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Evidence objects include provenance and explicitly mark `data_json_used=false`.",
            "- The index returns evidence records only; final-answer composition remains a separate step.",
            "- No final submission, official eval, scorer, or hidden-style test files are modified by this script.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
