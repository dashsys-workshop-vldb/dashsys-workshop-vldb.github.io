#!/usr/bin/env python
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dashagent.llm_client import DEFAULT_OPENAI_MODEL, DEFAULT_OPENROUTER_BASE_URL, DEFAULT_OPENROUTER_MODEL


DEFAULT_ENV_FILENAME = ".env.local"
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def project_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def load_local_env(
    project_root: Path | str | None = None,
    *,
    env_file: Path | str | None = None,
    override: bool = False,
) -> dict[str, Any]:
    """Load simple KEY=VALUE lines from .env.local without printing secrets.

    Existing environment variables win by default. Returned metadata contains
    key names only, never values.
    """

    root = Path(project_root) if project_root is not None else project_root_from_script()
    path = Path(env_file) if env_file is not None else root / DEFAULT_ENV_FILENAME
    result: dict[str, Any] = {
        "loaded": False,
        "path_exists": path.exists(),
        "source": None,
        "keys_loaded": [],
        "keys_skipped_existing": [],
        "keys_invalid": [],
    }
    if not path.exists():
        return result

    parsed_values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not _KEY_RE.match(key):
            result["keys_invalid"].append(key)
            continue
        value = _strip_quotes(value.strip())
        value = _expand_vars(value, parsed_values)
        parsed_values[key] = value
        if not override and os.environ.get(key):
            result["keys_skipped_existing"].append(key)
            continue
        os.environ[key] = value
        result["keys_loaded"].append(key)

    result["loaded"] = bool(result["keys_loaded"] or result["keys_skipped_existing"])
    result["source"] = ".env.local" if result["loaded"] else None
    return result


def llm_env_status(project_root: Path | str | None = None) -> dict[str, Any]:
    """Return a redacted LLM environment status suitable for CLI output."""

    preexisting_key = _visible_key_name()
    loaded = load_local_env(project_root)
    visible_key = _visible_key_name()
    provider = _provider()
    if preexisting_key:
        source = "environment"
    elif visible_key and visible_key in set(loaded.get("keys_loaded") or []):
        source = ".env.local"
    else:
        source = "none"
    return {
        "key_visible": bool(visible_key),
        "provider": provider,
        "base_url": _base_url(provider),
        "model": _model(provider),
        "source": source,
    }


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _expand_vars(value: str, parsed_values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return os.environ.get(name, parsed_values.get(name, ""))

    return _VAR_RE.sub(replace, value)


def _visible_key_name() -> str | None:
    if os.environ.get("OPENROUTER_API_KEY"):
        return "OPENROUTER_API_KEY"
    if os.environ.get("OPENAI_API_KEY"):
        return "OPENAI_API_KEY"
    return None


def _provider() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.environ.get("OPENAI_API_KEY"):
        if "openrouter.ai" in os.environ.get("OPENAI_BASE_URL", ""):
            return "openrouter"
        return "openai"
    return "none"


def _base_url(provider: str) -> str:
    if provider == "openrouter":
        return os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL
    if provider == "openai":
        return os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    return os.environ.get("OPENAI_BASE_URL") or ""


def _model(provider: str) -> str:
    if provider == "openrouter":
        return os.environ.get("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL
    if provider == "openai":
        return os.environ.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    return os.environ.get("OPENROUTER_MODEL") or os.environ.get("OPENAI_MODEL") or DEFAULT_OPENROUTER_MODEL


__all__ = ["load_local_env", "llm_env_status", "project_root_from_script"]
