#!/usr/bin/env python
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


REQUIRED_QUERY_FILES = ["metadata.json", "filled_system_prompt.txt", "trajectory.json"]


def main() -> int:
    config = Config.from_env(ROOT)
    final_dir = config.outputs_dir / "final_submission"
    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.mkdir(parents=True)

    preferred_strategy = os.getenv("DASHAGENT_SUBMISSION_STRATEGY", "SQL_FIRST_API_VERIFY")
    query_dirs = select_submission_query_dirs(
        discover_query_output_dirs(config.outputs_dir),
        preferred_strategy=preferred_strategy,
        require_complete_trajectory=True,
    )
    manifest_queries = []
    for index, source_dir in enumerate(query_dirs, start=1):
        target_id = f"query_{index:03d}"
        target_dir = final_dir / target_id
        target_dir.mkdir()
        checks = {"source_dir": str(source_dir), "files": {}, "trajectory_json_valid": False, "strategy": None}
        for filename in REQUIRED_QUERY_FILES:
            source = source_dir / filename
            exists = source.exists()
            checks["files"][filename] = exists
            if exists:
                shutil.copy2(source, target_dir / filename)
        trajectory_path = target_dir / "trajectory.json"
        if trajectory_path.exists():
            try:
                trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
                checks["trajectory_json_valid"] = True
                checks["strategy"] = trajectory.get("strategy")
                checks["original_query"] = trajectory.get("original_query")
            except json.JSONDecodeError:
                checks["trajectory_json_valid"] = False
        manifest_queries.append({"query_id": target_id, **checks})

    system_prompt = config.prompts_dir / "system_prompt_template.txt"
    if system_prompt.exists():
        shutil.copy2(system_prompt, final_dir / "system_prompt_template.txt")

    source_zip = config.outputs_dir / "source_code.zip"
    if source_zip.exists():
        shutil.copy2(source_zip, final_dir / "source_code.zip")

    no_secret_scan = scan_for_output_secrets(final_dir)
    manifest = {
        "total_number_of_queries": len(manifest_queries),
        "preferred_strategy": preferred_strategy,
        "queries": manifest_queries,
        "system_prompt_template_exists": (final_dir / "system_prompt_template.txt").exists(),
        "source_code_zip_exists": (final_dir / "source_code.zip").exists(),
        "no_secret_scan": no_secret_scan,
    }
    manifest = redact_secrets(manifest)
    manifest_path = config.outputs_dir / "final_submission_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps({"final_submission": str(final_dir), "manifest": str(manifest_path), **manifest}, indent=2, sort_keys=True))
    return 0 if no_secret_scan["ok"] else 1


def discover_query_output_dirs(outputs_dir: Path) -> list[Path]:
    candidates = []
    for path in outputs_dir.rglob("trajectory.json"):
        if any(part in {"final_submission", "source_code"} or part.startswith("probe") for part in path.parts):
            continue
        directory = path.parent
        if all((directory / filename).exists() for filename in REQUIRED_QUERY_FILES):
            candidates.append(directory)
    return sorted(candidates, key=lambda path: str(path))


def select_submission_query_dirs(
    query_dirs: list[Path],
    preferred_strategy: str,
    *,
    require_complete_trajectory: bool = False,
) -> list[Path]:
    grouped: dict[str, list[tuple[str | None, Path]]] = {}
    for directory in query_dirs:
        trajectory_path = directory / "trajectory.json"
        try:
            trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if require_complete_trajectory and not required_trajectory_fields_present(trajectory):
            continue
        key = str(trajectory.get("query_id") or trajectory.get("original_query") or directory.parent)
        strategy = trajectory.get("strategy")
        grouped.setdefault(key, []).append((strategy, directory))

    selected = []
    for entries in grouped.values():
        preferred = [directory for strategy, directory in entries if strategy == preferred_strategy]
        if preferred:
            selected.append(sorted(preferred, key=lambda path: str(path))[0])
        else:
            selected.append(sorted((directory for _, directory in entries), key=lambda path: str(path))[0])
    return sorted(selected, key=lambda path: str(path))


def required_trajectory_fields_present(trajectory: dict[str, Any]) -> bool:
    required = ["final_answer", "tool_call_count", "runtime", "estimated_tokens"]
    return all(key in trajectory for key in required)


def scan_for_output_secrets(final_dir: Path) -> dict[str, Any]:
    secret_markers = ["Bearer ", "CLIENT_SECRET=", "ACCESS_TOKEN=", "client_secret", "access_token"]
    hits = []
    for path in final_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".zip", ".png", ".jpg", ".jpeg", ".parquet"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in secret_markers:
            if marker in text and "[REDACTED]" not in text:
                hits.append({"file": str(path), "marker": marker})
    return {"ok": not hits, "hits": hits}


if __name__ == "__main__":
    raise SystemExit(main())
