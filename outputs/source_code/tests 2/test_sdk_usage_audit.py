from __future__ import annotations

import json
import re
from pathlib import Path

from dashagent.config import Config
from scripts.generate_sdk_usage_audit import generate_sdk_usage_audit


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_llm_source_has_no_direct_http_calls():
    patterns = [
        re.compile(r"\brequests\.post\b"),
        re.compile(r"\brequests\.request\b"),
        re.compile(r"/chat/completions"),
        re.compile(r"\bcurl\b"),
    ]
    runtime_files = [
        *ROOT.glob("dashagent/**/*.py"),
        *[
            path
            for path in ROOT.glob("scripts/*.py")
            if path.name
            not in {
                "generate_sdk_usage_audit.py",
            }
        ],
    ]
    offenders = []
    for path in runtime_files:
        text = path.read_text(encoding="utf-8")
        if path.name == "check_openai_compatible_llm.py":
            assert "run_llm_sdk_backend_check" in text
            assert "/chat/completions" not in text
            continue
        for pattern in patterns:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(ROOT)}:{pattern.pattern}")
    assert offenders == []


def test_sdk_usage_audit_detects_direct_llm_http_in_temp_project(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "outputs").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "DBSnapshot").mkdir(parents=True)
    (tmp_path / "data" / "data.json").write_text("[]", encoding="utf-8")
    (tmp_path / "scripts" / "bad_llm.py").write_text(
        "import requests\nrequests.post('https://api.openai.com/v1/chat/completions')\n",
        encoding="utf-8",
    )
    config = Config(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        dbsnapshot_dir=tmp_path / "data" / "DBSnapshot",
        data_json_path=tmp_path / "data" / "data.json",
        outputs_dir=tmp_path / "outputs",
        prompts_dir=tmp_path / "prompts",
    )

    report = generate_sdk_usage_audit(config)

    assert report["summary"]["runtime_llm_direct_http_hits"] >= 1
    assert any(hit["classification"] == "llm_runtime_refactor_required" for hit in report["hits"])


def test_current_sdk_usage_audit_has_zero_runtime_direct_llm_hits():
    report = generate_sdk_usage_audit()
    assert report["summary"]["runtime_llm_direct_http_hits"] == 0
    assert report["all_llm_calls_sdk_based"] is True
    text = json.dumps(report)
    assert "Authorization" + ": " + "Bearer " not in text
