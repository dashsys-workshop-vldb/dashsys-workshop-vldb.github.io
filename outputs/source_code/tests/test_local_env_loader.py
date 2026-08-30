from __future__ import annotations

import json

from scripts import check_llm_env
from scripts.load_local_env import load_local_env, llm_env_status
from scripts.run_llm_answer_rewrite_search import _invalid_json_failure_category, _provider_failure_category, run_llm_answer_rewrite_search


def _clear_llm_env(monkeypatch):
    for key in [
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_MODEL",
        "OPENAI_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_BASE_URL",
        "LLM_PROVIDER",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_env_local_is_gitignored_and_env_example_is_trackable():
    gitignore = open(".gitignore", encoding="utf-8").read().splitlines()
    assert ".env.local" in gitignore
    assert "!.env.example" in gitignore


def test_env_example_contains_placeholders_only():
    text = open(".env.example", encoding="utf-8").read()
    assert "OPENAI_API_KEY=put_your_key_here" in text
    assert "OPENAI_BASE_URL=https://photos-hewlett-safely-friends.trycloudflare.com/v1" in text
    assert "OPENAI_MODEL=qwen2.5-32b-instruct" in text
    assert "ANTHROPIC_API_KEY=put_your_anthropic_key_here" in text
    assert "sk-" not in text
    assert "sk_or" not in text


def test_loader_reads_env_local_without_printing_or_overriding(monkeypatch, tmp_path, capsys):
    _clear_llm_env(monkeypatch)
    env_path = tmp_path / ".env.local"
    env_path.write_text(
        "\n".join(
            [
                "# local only",
                "OPENROUTER_API_KEY=unit-test-openrouter-key",
                "OPENAI_API_KEY=${OPENROUTER_API_KEY}",
                "OPENAI_BASE_URL=https://openrouter.ai/api/v1",
                "OPENROUTER_MODEL=test/model",
            ]
        ),
        encoding="utf-8",
    )

    result = load_local_env(tmp_path)
    captured = capsys.readouterr()

    assert result["loaded"] is True
    assert "OPENROUTER_API_KEY" in result["keys_loaded"]
    assert captured.out == ""
    assert captured.err == ""
    assert "unit-test-openrouter-key" not in json.dumps(result)

    monkeypatch.setenv("OPENROUTER_MODEL", "already-set/model")
    result = load_local_env(tmp_path)
    assert "OPENROUTER_MODEL" in result["keys_skipped_existing"]
    assert result["keys_loaded"] == []
    assert result["keys_skipped_existing"]


def test_check_llm_env_reports_visibility_without_leaking_key(monkeypatch, tmp_path, capsys):
    _clear_llm_env(monkeypatch)
    (tmp_path / ".env.local").write_text(
        "OPENROUTER_API_KEY=unit-test-openrouter-key\nOPENAI_BASE_URL=https://openrouter.ai/api/v1\nOPENROUTER_MODEL=test/model\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(check_llm_env, "ROOT", tmp_path)
    assert check_llm_env.main() == 0
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload == {
        "base_url": "https://openrouter.ai/api/v1",
        "key_visible": True,
        "model": "test/model",
        "provider": "openrouter",
        "source": ".env.local",
    }
    assert "unit-test-openrouter-key" not in output


def test_llm_env_status_prefers_existing_environment(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "existing-openrouter-key")
    (tmp_path / ".env.local").write_text("OPENROUTER_API_KEY=file-openrouter-key\n", encoding="utf-8")

    status = llm_env_status(tmp_path)

    assert status["key_visible"] is True
    assert status["provider"] == "openrouter"
    assert status["source"] == "environment"
    assert "existing-openrouter-key" not in json.dumps(status)
    assert "file-openrouter-key" not in json.dumps(status)


def test_llm_answer_rewrite_search_uses_env_local_when_shell_env_absent(monkeypatch, tiny_project):
    _clear_llm_env(monkeypatch)
    (tiny_project.project_root / ".env.local").write_text(
        "OPENROUTER_API_KEY=unit-test-openrouter-key\nOPENAI_BASE_URL=https://openrouter.ai/api/v1\nOPENROUTER_MODEL=fake/model\n",
        encoding="utf-8",
    )
    output_dir = tiny_project.outputs_dir / "eval" / "tiny_001" / "sql_first_api_verify"
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory = {
        "query_id": "tiny_001",
        "original_query": "How many campaigns are there?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "steps": [],
        "final_answer": "Dry-run evidence is unavailable.",
        "runtime": 0.01,
        "tool_call_count": 0,
        "estimated_tokens": 50,
        "errors": [],
    }
    (output_dir / "metadata.json").write_text(json.dumps({"query_id": "tiny_001"}), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("prompt", encoding="utf-8")
    (output_dir / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    (tiny_project.outputs_dir / "eval_results_strict.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "query": "How many campaigns are there?",
                        "strategy": "SQL_FIRST_API_VERIFY",
                        "output_dir": str(output_dir),
                        "final_score": 0.5,
                        "correctness_score": 0.55,
                        "answer_score": 0.2,
                        "estimated_tokens": 50,
                        "runtime": 0.01,
                        "tool_call_count": 0,
                    }
                ],
                "summary": {},
            }
        ),
        encoding="utf-8",
    )
    (tiny_project.outputs_dir / "unsafe_answer_candidate_analysis.json").write_text(
        json.dumps({"rows": [{"query_id": "tiny_001", "supportable_answer_delta": 0.2}], "summary": {}}),
        encoding="utf-8",
    )

    class FakeClient:
        def available(self):
            return True

        def model_name(self):
            return "fake/model"

        def generate_messages(self, messages):
            return {"ok": False, "error": "provider unavailable"}

    monkeypatch.setattr("scripts.run_llm_answer_rewrite_search.get_llm_client", lambda provider=None: FakeClient())

    payload = run_llm_answer_rewrite_search(tiny_project)

    assert payload["summary"]["status"] == "completed"
    assert payload["provider"] == "openrouter"
    assert payload["model"] == "fake/model"
    assert payload["summary"]["failure_category_counts"]["provider_unavailable"] == 1
    assert "unit-test-openrouter-key" not in json.dumps(payload)


def test_llm_answer_rewrite_search_uses_reduced_budget_for_openrouter_free(monkeypatch, tiny_project):
    _clear_llm_env(monkeypatch)
    (tiny_project.project_root / ".env.local").write_text(
        "OPENROUTER_API_KEY=unit-test-openrouter-key\nOPENAI_BASE_URL=https://openrouter.ai/api/v1\nOPENROUTER_MODEL=openrouter/free\n",
        encoding="utf-8",
    )
    output_dir = tiny_project.outputs_dir / "eval" / "tiny_001" / "sql_first_api_verify"
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory = {
        "query_id": "tiny_001",
        "original_query": "How many campaigns are there?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "steps": [],
        "final_answer": "Dry-run evidence is unavailable.",
        "runtime": 0.01,
        "tool_call_count": 0,
        "estimated_tokens": 50,
        "errors": [],
    }
    (output_dir / "metadata.json").write_text(json.dumps({"query_id": "tiny_001"}), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("prompt", encoding="utf-8")
    (output_dir / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    (tiny_project.outputs_dir / "eval_results_strict.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "query": "How many campaigns are there?",
                        "strategy": "SQL_FIRST_API_VERIFY",
                        "output_dir": str(output_dir),
                        "final_score": 0.5,
                        "correctness_score": 0.55,
                        "answer_score": 0.2,
                        "estimated_tokens": 50,
                        "runtime": 0.01,
                        "tool_call_count": 0,
                    }
                ],
                "summary": {},
            }
        ),
        encoding="utf-8",
    )
    (tiny_project.outputs_dir / "unsafe_answer_candidate_analysis.json").write_text(
        json.dumps({"rows": [{"query_id": "tiny_001", "supportable_answer_delta": 0.2}], "summary": {}}),
        encoding="utf-8",
    )

    class FakeClient:
        calls = 0

        def available(self):
            return True

        def model_name(self):
            return "openrouter/free"

        def generate_messages(self, messages):
            self.calls += 1
            return {"ok": True, "content": "not json"}

    client = FakeClient()
    monkeypatch.setattr("scripts.run_llm_answer_rewrite_search.get_llm_client", lambda provider=None: client)

    payload = run_llm_answer_rewrite_search(tiny_project)

    assert payload["budget"]["max_rewrites_per_row"] == 3
    assert payload["budget"]["max_retries_per_row"] == 1
    assert payload["summary"]["failure_category_counts"]["weak_model_invalid_json"] == 1
    assert client.calls == 1


def test_llm_answer_rewrite_failure_category_helpers():
    assert _provider_failure_category("429 rate limit exceeded") == "rate_limit"
    assert _provider_failure_category("provider unavailable for this model") == "provider_unavailable"
    assert _provider_failure_category("connection reset") == "provider_error"
    assert _invalid_json_failure_category("openrouter/free", "invalid_json:no_json_object") == "weak_model_invalid_json"
    assert _invalid_json_failure_category("other/model", "invalid_json:no_json_object") == "invalid_json"
