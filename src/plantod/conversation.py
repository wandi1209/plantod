"""Multi-turn conversation memory for the interactive session (PRD 32.4).

Keeps a rolling transcript (last N turns) so follow-up requests carry context —
e.g. "now add logout too" understands the prior "add login" turn.
"""

from __future__ import annotations

from .schemas import Turn

MAX_TURNS = 40           # hard cap kept in session.json
CONTEXT_TURNS = 6        # how many recent turns are fed to the planner


def record(state, role: str, text: str) -> None:
    """Append a turn and trim to the last MAX_TURNS. Caller persists via state.save()."""
    state.session.turns.append(Turn(role=role, text=text))
    if len(state.session.turns) > MAX_TURNS:
        state.session.turns[:] = state.session.turns[-MAX_TURNS:]


def build_context(state, n: int = CONTEXT_TURNS) -> str:
    """Format the last `n` turns as planner context (empty string if none)."""
    turns = state.session.turns[-n:]
    if not turns:
        return ""
    lines = [f"{t.role}: {t.text}" for t in turns]
    return "\n".join(lines)
