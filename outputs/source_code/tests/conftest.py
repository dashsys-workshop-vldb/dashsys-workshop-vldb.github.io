from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from dashagent.config import Config


@pytest.fixture
def tiny_project(tmp_path: Path) -> Config:
    data_dir = tmp_path / "data"
    db_dir = data_dir / "DBSnapshot"
    outputs_dir = tmp_path / "outputs"
    prompts_dir = tmp_path / "prompts"
    db_dir.mkdir(parents=True)
    prompts_dir.mkdir()
    (prompts_dir / "system_prompt_template.txt").write_text("Metadata:\n{metadata_json}\n", encoding="utf-8")

    pd.DataFrame(
        [
            {"campaign_id": "c1", "name": "Birthday Message", "status": "draft", "lastdeployedtime": None},
            {"campaign_id": "c2", "name": "Welcome Journey", "status": "published", "lastdeployedtime": "2026-01-01"},
        ]
    ).to_parquet(db_dir / "dim_campaign.parquet", index=False)
    pd.DataFrame(
        [
            {"segment_id": "s1", "name": "High Value", "profile_count": 12},
            {"segment_id": "s2", "name": "Recent Buyers", "profile_count": 8},
        ]
    ).to_parquet(db_dir / "dim_segment.parquet", index=False)
    (data_dir / "data.json").write_text(
        json.dumps(
            [
                {
                    "id": "tiny_001",
                    "query": "How many campaigns are there?",
                    "gold_sql": "SELECT COUNT(*) AS count FROM dim_campaign",
                    "answer": "2",
                }
            ]
        ),
        encoding="utf-8",
    )

    return Config(
        project_root=tmp_path,
        data_dir=data_dir,
        dbsnapshot_dir=db_dir,
        data_json_path=data_dir / "data.json",
        outputs_dir=outputs_dir,
        prompts_dir=prompts_dir,
    )
