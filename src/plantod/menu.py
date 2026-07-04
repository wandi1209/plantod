"""Inline arrow-key selection menu (prompt_toolkit).

`select("Provider", ["claude-code", ...])` renders an inline list; move with ↑/↓,
type to filter, Enter to confirm. Long lists scroll within a fixed viewport.
Falls back to numbered text input when stdin isn't a TTY or prompt_toolkit is
unavailable.
"""

from __future__ import annotations

import sys

_MAX_VISIBLE = 10
_CANCEL = object()


def _norm(options: list) -> tuple[list[str], list]:
    labels, values = [], []
    for o in options:
        if isinstance(o, tuple):
            labels.append(str(o[0]))
            values.append(o[1])
        else:
            labels.append(str(o))
            values.append(o)
    return labels, values


def select(title: str, options: list, default=None):
    """Return the chosen value. Raises KeyboardInterrupt if cancelled."""
    labels, values = _norm(options)
    if not labels:
        raise KeyboardInterrupt
    start = values.index(default) if default in values else 0

    if not sys.stdin.isatty():
        return _fallback(title, labels, values, start)
    try:
        return _interactive(title, labels, values, start)
    except ImportError:
        return _fallback(title, labels, values, start)


def _interactive(title, labels, values, start):
    from prompt_toolkit.application import Application
    from prompt_toolkit.formatted_text import to_formatted_text
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    st = {"filter": "", "i": start}

    def filtered() -> list[int]:
        f = st["filter"].lower()
        idxs = [i for i, l in enumerate(labels) if f in l.lower()]
        return idxs or []

    def render():
        idxs = filtered()
        if st["i"] >= len(idxs):
            st["i"] = max(0, len(idxs) - 1)
        frags = []
        hint = f"  (type to filter, ↑↓ move, Enter select)" if len(labels) > _MAX_VISIBLE else ""
        if st["filter"]:
            frags.append(("class:filter", f" /{st['filter']}\n"))
        elif hint:
            frags.append(("class:hint", hint + "\n"))
        if not idxs:
            frags.append(("", "   (no match)\n"))
            return to_formatted_text(frags)
        top = _clamp(st["i"] - _MAX_VISIBLE // 2, 0, max(0, len(idxs) - _MAX_VISIBLE))
        for row, real in enumerate(idxs[top:top + _MAX_VISIBLE]):
            marker = "❯" if top + row == st["i"] else " "
            style = "reverse" if top + row == st["i"] else ""
            frags.append((style, f" {marker} {labels[real]}\n"))
        if len(idxs) > _MAX_VISIBLE:
            frags.append(("class:hint", f"   … {len(idxs)} matches\n"))
        return to_formatted_text(frags)

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("c-p")
    def _(_e):
        st["i"] = max(0, st["i"] - 1)

    @kb.add("down")
    @kb.add("c-n")
    def _(_e):
        st["i"] = min(len(filtered()) - 1, st["i"] + 1)

    @kb.add("backspace")
    def _(_e):
        st["filter"] = st["filter"][:-1]
        st["i"] = 0

    @kb.add("enter")
    def _(e):
        idxs = filtered()
        if idxs:
            e.app.exit(result=values[idxs[st["i"]]])

    @kb.add("c-c")
    @kb.add("escape")
    def _(e):
        e.app.exit(result=_CANCEL)

    @kb.add("<any>")
    def _(e):
        ch = e.data
        if ch and ch.isprintable():
            st["filter"] += ch
            st["i"] = 0

    header = Window(FormattedTextControl(lambda: title), height=1) if title else None
    body = Window(FormattedTextControl(render, focusable=True))
    root = HSplit([w for w in (header, body) if w is not None])
    app = Application(layout=Layout(root), key_bindings=kb, full_screen=False)
    result = app.run()
    if result is _CANCEL:
        raise KeyboardInterrupt
    return result


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _fallback(title: str, labels: list[str], values: list, start: int):
    if title:
        print(title)
    for i, label in enumerate(labels):
        marker = "*" if i == start else " "
        print(f"  {marker} {i + 1}) {label}")
    raw = input(f"Choose [1-{len(labels)}] (default {start + 1}): ").strip()
    if not raw:
        return values[start]
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(values):
            return values[idx]
    except ValueError:
        pass
    return values[start]
