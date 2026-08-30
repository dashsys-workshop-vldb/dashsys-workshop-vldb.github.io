from __future__ import annotations

from dashagent.eval_harness import score_answer_strict, score_api_strict, score_sql_strict
from dashagent.executor import AgentExecutor


def test_strict_missing_gold_is_unscored(tiny_project):
    executor = AgentExecutor(tiny_project)
    score, reason = score_sql_strict(executor.db, "SELECT 1", None)
    assert score is None
    assert "unscored" in reason


def test_strict_answer_caps_fuzzy_only_score():
    score, _ = score_answer_strict("this is vaguely similar text", "completely different expected answer")
    assert score is not None
    assert score <= 0.25


def test_strict_api_wrong_path_penalized():
    generated = [{"method": "GET", "path": "/wrong/path", "params": {"limit": 10}}]
    gold = [{"method": "GET", "path": "/data/core/ups/config/mergePolicies", "params": {"limit": 10}}]
    score, _ = score_api_strict(generated, gold)
    assert score is not None
    assert score < 0.7
