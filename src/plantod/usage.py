"""Estimated token accounting.

Provider CLIs are driven headless and do not reliably report token counts, so
PLANTOD *estimates* usage from text length (~4 chars/token). These are rough
figures for relative comparison, not billing-grade numbers.
"""

from __future__ import annotations

from .schemas import Config, UsageEntry

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def estimate_cost(entries: list[UsageEntry], config: Config) -> float | None:
    """USD estimate from config.prices, or None if no prices configured."""
    if not config.prices:
        return None
    total = 0.0
    for e in entries:
        rate = config.prices.get(e.provider)
        if not rate:
            continue
        in_rate, out_rate = (rate + [0, 0])[:2]
        total += e.tokens_in / 1_000_000 * in_rate
        total += e.tokens_out / 1_000_000 * out_rate
    return round(total, 4)


def summarize(entries: list[UsageEntry]) -> dict[str, dict[str, int]]:
    """Aggregate tokens per provider: {provider: {in, out, calls}}."""
    agg: dict[str, dict[str, int]] = {}
    for e in entries:
        a = agg.setdefault(e.provider, {"in": 0, "out": 0, "calls": 0})
        a["in"] += e.tokens_in
        a["out"] += e.tokens_out
        a["calls"] += 1
    return agg
