"""Model backend adapters (planner / executor / reviewer)."""

from .base import ExecResult, ModelAdapter, PlanResult, ReviewResult
from .registry import resolve

__all__ = ["ModelAdapter", "PlanResult", "ExecResult", "ReviewResult", "resolve"]
