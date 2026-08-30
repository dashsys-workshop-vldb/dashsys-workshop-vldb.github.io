from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json_md(stem: str, payload: dict[str, Any], lines: list[str], reports_dir: Path | None = None) -> None:
    target = reports_dir or ROOT / "outputs" / "reports"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{stem}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (target / f"{stem}.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_organizer_prompts() -> list[dict[str, Any]]:
    payload = read_json(ROOT / "data" / "data.json")
    rows = payload if isinstance(payload, list) else payload.get("examples", []) if isinstance(payload, dict) else []
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        prompt = row.get("query") or row.get("question") or row.get("input") or row.get("nl_query")
        if prompt:
            out.append({"prompt_id": str(row.get("id") or row.get("query_id") or f"example_{idx:03d}"), "prompt": str(prompt), "dataset": "organizer_35"})
    return out


def load_500_runtime_prompts() -> list[dict[str, Any]]:
    rows = read_jsonl(ROOT / "data" / "benchmarks" / "dashagent_500_prompt_suite.jsonl")
    for row in rows:
        row["dataset"] = "internal_500"
    return rows


def load_500_gold_by_id() -> dict[str, dict[str, Any]]:
    return {row["prompt_id"]: row for row in read_jsonl(ROOT / "data" / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl") if "prompt_id" in row}


def counter_dict(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def trajectory_files(dataset_prefix: str = "example_", strategy: str | None = None) -> list[Path]:
    root = ROOT / "outputs" / "eval"
    if not root.exists():
        return []
    files = []
    for path in root.glob(f"{dataset_prefix}*/**/trajectory.json"):
        if strategy and path.parent.name != strategy:
            continue
        files.append(path)
    return sorted(files)


def load_trajectory(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def checkpoint_names(trajectory: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in trajectory.get("checkpoints") or []:
        if isinstance(item, dict):
            out.append(str(item.get("checkpoint_id") or item.get("name") or item.get("checkpoint") or ""))
    return out


def compact_prompt(prompt: str, limit: int = 160) -> str:
    text = " ".join(str(prompt or "").split())
    return text[:limit] + ("..." if len(text) > limit else "")


def required_fact_coverage(answer: str, required_facts: list[Any]) -> tuple[float, list[str]]:
    if not required_facts:
        return 1.0, []
    normalized_answer = normalize_text(answer)
    missing = [str(fact) for fact in required_facts if normalize_text(str(fact)) not in normalized_answer]
    return round((len(required_facts) - len(missing)) / len(required_facts), 4), missing


def forbidden_claim_hits(answer: str, forbidden_claims: list[Any]) -> list[str]:
    normalized_answer = normalize_text(answer)
    return [str(claim) for claim in forbidden_claims if normalize_text(str(claim)) in normalized_answer]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def safe_summary_metrics(report: dict[str, Any], strategy: str) -> dict[str, Any]:
    return ((report.get("summary") or {}).get("by_strategy") or {}).get(strategy, {})
