#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.score_provenance import build_score_provenance, infer_score_provenance


REPORT_SPECS = [
    ("organizer_strict", ROOT / "outputs" / "eval_results_strict.json"),
    ("internal_500_heuristic", ROOT / "outputs" / "reports" / "dashagent_500_prompt_suite_eval_real.json"),
    ("internal_500_organizer_style", ROOT / "outputs" / "reports" / "dashagent_500_organizer_style_strict_comparison.json"),
    ("simulated_trace", ROOT / "outputs" / "reports" / "dashagent_500_prompt_suite_eval_simulated.json"),
    ("hidden_style", ROOT / "outputs" / "hidden_style_eval.json"),
]


def run_audit(reports_dir: Path = ROOT / "outputs" / "reports") -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for source, path in REPORT_SPECS:
        if path.exists():
            payload = _load_json(path)
            if isinstance(payload, dict):
                inferred = infer_score_provenance(payload, path=path.as_posix())
                if inferred.score_source != source:
                    inferred = build_score_provenance(
                        score_source=source,
                        real_agent_execution=inferred.real_agent_execution,
                        synthetic_trace=inferred.synthetic_trace,
                        runtime_gold_visible=inferred.runtime_gold_visible,
                        grading_type=inferred.grading_type,
                        evaluator_script=inferred.evaluator_script,
                        dataset_path=inferred.dataset_path,
                    )
                entry = inferred.to_dict()
                entry["report_path"] = path.as_posix()
                entry["exists"] = True
                entries.append(entry)
        else:
            entries.append(
                build_score_provenance(
                    score_source=source,
                    real_agent_execution=False,
                    synthetic_trace=source == "simulated_trace",
                    grading_type="missing_report",
                    evaluator_script="",
                    dataset_path="",
                    promotion_eligible=False,
                ).to_dict()
                | {"report_path": path.as_posix(), "exists": False}
            )
    summary = {
        "report_count": len(entries),
        "promotion_eligible_reports": sum(1 for entry in entries if entry["promotion_eligible"]),
        "promotion_ineligible_simulated_reports": sum(1 for entry in entries if entry["score_source"] == "simulated_trace" and not entry["promotion_eligible"]),
        "organizer_equivalent_reports": sum(1 for entry in entries if entry["organizer_equivalent"]),
        "runtime_gold_visible_count": sum(1 for entry in entries if entry["runtime_gold_visible"]),
        "real_agent_execution_reports": sum(1 for entry in entries if entry["real_agent_execution"]),
    }
    report = {"report_type": "score_provenance_audit", "entries": entries, "summary": summary}
    write_report(report, reports_dir)
    return report


def write_report(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "score_provenance_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Score Provenance Audit",
        "",
        "| Source | Exists | Real Agent | Synthetic | Organizer Equivalent | Promotion Eligible |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for entry in report["entries"]:
        lines.append(
            f"| `{entry['score_source']}` | `{str(entry['exists']).lower()}` | `{str(entry['real_agent_execution']).lower()}` | "
            f"`{str(entry['synthetic_trace']).lower()}` | `{str(entry['organizer_equivalent']).lower()}` | "
            f"`{str(entry['promotion_eligible']).lower()}` |"
        )
    lines.extend(["", "Simulated trace reports are diagnostic-only and promotion-ineligible."])
    (reports_dir / "score_provenance_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "outputs" / "reports")
    args = parser.parse_args()
    report = run_audit(args.reports_dir)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
