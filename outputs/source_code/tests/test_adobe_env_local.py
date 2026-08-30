from __future__ import annotations

import json
from pathlib import Path

from dashagent.adobe_env import format_adobe_readiness_for_report
from scripts import check_adobe_env_local


def test_env_local_example_exists_and_has_placeholders_only():
    text = Path('.env.local.example').read_text(encoding='utf-8')
    for key in [
        'ADOBE_ACCESS_TOKEN =',
        'ADOBE_API_KEY =',
        'ADOBE_ORG_ID =',
        'ADOBE_SANDBOX_NAME =',
        'ADOBE_BASE_URL = https://platform.adobe.io',
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
        'ADOBE_ACCESS_TOKEN','ACCESS_TOKEN','ADOBE_API_KEY','CLIENT_ID','CLIENT_SECRET','ADOBE_CLIENT_ID','ADOBE_CLIENT_SECRET','ADOBE_ORG_ID','IMS_ORG','ADOBE_SANDBOX_NAME','SANDBOX','ADOBE_BASE_URL'
    ]:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / '.env.local').write_text(
        'ADOBE_ACCESS_TOKEN = test-token-value\nADOBE_API_KEY = test-api-key\nADOBE_ORG_ID = test-org\nADOBE_SANDBOX_NAME = prod\nADOBE_BASE_URL = https://platform.adobe.io\n',
        encoding='utf-8'
    )
    monkeypatch.setattr(check_adobe_env_local, 'ROOT', tmp_path)
    assert check_adobe_env_local.main() == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload['ready_for_live_adobe_api_smoke'] is True
    assert payload['auth_mode'] == 'access_token'
    assert payload['authorization_constructible'] is True
    assert payload['credential_ready'] is True
    assert payload['sandbox_ready'] is True
    assert payload['ready_for_sandbox_endpoints'] is True
    assert _source(payload, 'access_token') == 'primary'
    assert _header(payload, 'Authorization') is True
    assert 'test-token-value' not in out
    assert 'test-api-key' not in out
    assert 'test-org' not in out
    assert 'prod' not in out


def test_check_adobe_env_local_accepts_client_credentials_without_access_token(monkeypatch, tmp_path, capsys):
    for key in [
        'ADOBE_ACCESS_TOKEN','ACCESS_TOKEN','ADOBE_API_KEY','CLIENT_ID','CLIENT_SECRET','ADOBE_CLIENT_ID','ADOBE_CLIENT_SECRET','ADOBE_ORG_ID','IMS_ORG','ADOBE_SANDBOX_NAME','SANDBOX','ADOBE_BASE_URL'
    ]:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / '.env.local').write_text(
        'CLIENT_ID=test-client-id\nCLIENT_SECRET=test-client-secret\nIMS_ORG=test-org\nSANDBOX=prod\n',
        encoding='utf-8'
    )
    monkeypatch.setattr(check_adobe_env_local, 'ROOT', tmp_path)
    assert check_adobe_env_local.main() == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload['auth_mode'] == 'client_credentials'
    assert payload['authorization_constructible'] is True
    assert payload['credential_ready'] is True
    assert payload['sandbox_ready'] is True
    assert payload['ready_for_live_adobe_api_smoke'] is True
    assert payload['ready_for_sandbox_endpoints'] is True
    assert _source(payload, 'client_id') == 'alias'
    assert _source(payload, 'client_secret') == 'alias'
    assert _source(payload, 'base_url') == 'default'
    assert _source(payload, 'scopes') == 'default'
    assert 'test-client-id' not in out
    assert 'test-client-secret' not in out
    assert 'test-org' not in out
    assert 'prod' not in out


def test_check_adobe_env_local_missing_auth_not_ready(monkeypatch, tmp_path, capsys):
    for key in [
        'ADOBE_ACCESS_TOKEN','ACCESS_TOKEN','ADOBE_API_KEY','CLIENT_ID','CLIENT_SECRET','ADOBE_CLIENT_ID','ADOBE_CLIENT_SECRET','ADOBE_ORG_ID','IMS_ORG','ADOBE_SANDBOX_NAME','SANDBOX','ADOBE_BASE_URL'
    ]:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / '.env.local').write_text('ADOBE_ORG_ID=test-org\nADOBE_SANDBOX_NAME=prod\n', encoding='utf-8')
    monkeypatch.setattr(check_adobe_env_local, 'ROOT', tmp_path)
    assert check_adobe_env_local.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['auth_mode'] == 'missing'
    assert payload['authorization_constructible'] is False
    assert payload['credential_ready'] is False
    assert payload['sandbox_ready'] is True
    assert payload['ready_for_live_adobe_api_smoke'] is False


def test_report_formatter_uses_only_source_labels_and_booleans():
    readiness = {
        'auth_mode': 'client_credentials',
        'authorization_constructible': True,
        'env_names_detected': {
            'access_token': 'missing',
            'api_key': 'alias',
            'client_id': 'alias',
            'client_secret': 'alias',
            'org_id': 'alias',
            'sandbox_name': 'alias',
            'base_url': 'default',
            'scopes': 'default',
        },
        'headers_constructible': {
            'Authorization': True,
            'x-api-key': True,
            'x-gw-ims-org-id': True,
            'x-sandbox-name': True,
            'Content-Type': True,
        },
        'credential_ready': True,
        'sandbox_ready': True,
        'ready_for_live_adobe_api_smoke': True,
        'ready_for_sandbox_endpoints': True,
    }
    formatted = format_adobe_readiness_for_report(readiness)
    rendered = json.dumps(formatted)
    assert 'org_id' not in rendered
    assert 'sandbox_name' not in rendered
    assert '[MASKED_PREFIX]' not in rendered
    assert _source(formatted, 'organization') == 'alias'
    assert _source(formatted, 'sandbox') == 'alias'
    assert _header(formatted, 'x-gw-ims-org-id') is True


def _source(payload: dict, name: str) -> str:
    return next(item['source'] for item in payload['detected_env_sources'] if item['name'] == name)


def _header(payload: dict, header_name: str) -> bool:
    return next(item['constructible'] for item in payload['header_constructibility'] if item['header_name'] == header_name)
