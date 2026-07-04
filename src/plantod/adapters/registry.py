"""Resolve a role + config into a concrete ModelAdapter (PRD NFR-03)."""

from __future__ import annotations

from ..schemas import Config, Role
from .base import ModelAdapter
from .mock import MockAdapter


def resolve(role: Role, config: Config) -> ModelAdapter:
    driver = {
        Role.planner: config.planner_driver,
        Role.executor: config.executor_driver,
        Role.reviewer: config.reviewer_driver,
    }[role]

    if driver == "mock":
        return MockAdapter()
    if driver == "claude":
        from .claude import ClaudeAdapter

        return ClaudeAdapter(model=config.claude_model)
    if driver == "opencode":
        from .opencode import OpenCodeAdapter

        return OpenCodeAdapter(model=config.executor, timeout_s=config.exec_timeout_s)
    raise ValueError(f"unknown driver '{driver}' for role {role.value}")
