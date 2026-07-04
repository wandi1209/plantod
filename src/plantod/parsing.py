"""Tolerant extraction of a JSON object from model output (PRD 24: structured output).

Models return markdown prose + a fenced ```json block. Parse defensively so a
little surrounding chatter never breaks the pipeline (Technical Risk PRD 23).
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Return the first JSON value found in `text`, or raise ValueError."""
    # 1) fenced code block
    m = _FENCE_RE.search(text)
    candidates = [m.group(1)] if m else []
    # 2) fallback: first {...} or [...] span
    if not candidates:
        start = min(
            (i for i in (text.find("{"), text.find("[")) if i != -1),
            default=-1,
        )
        if start != -1:
            candidates.append(text[start:])
    for cand in candidates:
        cand = cand.strip()
        # trim trailing junk by walking back to a balanced end
        for end in range(len(cand), 0, -1):
            try:
                return json.loads(cand[:end])
            except json.JSONDecodeError:
                continue
    raise ValueError("no parseable JSON found in model output")
