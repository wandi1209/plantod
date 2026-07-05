"""Provider readiness checks — verify the configured CLIs are installed."""

from __future__ import annotations

import shutil

from .adapters.cliagent import provider_binary
from .schemas import Config

_ROLES = ("planner", "executor", "reviewer")


def check_providers(config: Config) -> list[dict]:
    """One row per role: {role, provider, binary, ok}."""
    rows = []
    for role in _ROLES:
        provider = getattr(config, role).provider
        if provider == "mock":
            rows.append({"role": role, "provider": provider, "binary": None, "ok": True})
            continue
        binary = provider_binary(provider)
        ok = bool(binary) and shutil.which(binary) is not None
        rows.append({"role": role, "provider": provider, "binary": binary, "ok": ok})
    return rows


def missing(config: Config) -> list[dict]:
    """Rows whose provider CLI is not installed."""
    return [r for r in check_providers(config) if not r["ok"]]
