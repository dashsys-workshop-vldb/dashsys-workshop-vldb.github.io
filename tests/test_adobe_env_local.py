from __future__ import annotations

import json
from pathlib import Path

from scripts import check_adobe_env_local


def test_env_local_example_exists_and_has_placeholders_only():
    text = Path('.env.local.example').read_text(encoding='utf-8')
    for key in [
        'ADOBE_ACCESS_TOKEN=',
        'ADOBE_API_KEY=',
        'ADOBE_ORG_ID=',
        'ADOBE_SANDBOX_NAME=',
        'ADOBE_BASE_URL=https://platform.adobe.io',
    ]:
        assert key in text
    assert 'Bearer ' not in text
    assert 'sk-' not in text


def test_gitignore_rules_for_env_local_and_example():
    lines = Path('.gitignore').read_text(encoding='utf-8').splitlines()
    assert '.env.local' in lines
    assert '.env.*.local' in lines
    assert '*.local.env' in lines
    assert '!.env.local.example' in lines


def test_check_adobe_env_local_reports_presence_only(monkeypatch, tmp_path, capsys):
    for key in [
        'ADOBE_ACCESS_TOKEN','ACCESS_TOKEN','ADOBE_API_KEY','CLIENT_ID','ADOBE_ORG_ID','IMS_ORG','ADOBE_SANDBOX_NAME','SANDBOX','ADOBE_BASE_URL'
    ]:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / '.env.local').write_text(
        'ADOBE_ACCESS_TOKEN=test-token-value\nADOBE_API_KEY=test-api-key\nADOBE_ORG_ID=test-org\nADOBE_SANDBOX_NAME=prod\nADOBE_BASE_URL=https://platform.adobe.io\n',
        encoding='utf-8'
    )
    monkeypatch.setattr(check_adobe_env_local, 'ROOT', tmp_path)
    assert check_adobe_env_local.main() == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload['ready_for_live_adobe_api_smoke'] is True
    assert payload['vars']['ADOBE_ACCESS_TOKEN'] == 'present'
    assert payload['headers_constructible']['Authorization'] is True
    assert 'test-token-value' not in out
    assert 'test-api-key' not in out
