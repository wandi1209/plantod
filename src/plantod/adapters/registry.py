"""Resolve a role + config into a concrete ModelAdapter (PRD NFR-03)."""

from __future__ import annotations

from ..schemas import Config, Role
from .base import ModelAdapter
from .mock import MockAdapter


def resolve(role: Role, config: Config) -> ModelAdapter:
    backend = config.backend(role)
    if backend.provider == "mock":
        return MockAdapter()
    from .cliagent import CliAgent

    return CliAgent(
        provider=backend.provider,
        model=backend.model,
        timeout_s=config.exec_timeout_s,
    )
