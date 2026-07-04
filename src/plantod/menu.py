"""Inline arrow-key selection menu (prompt_toolkit).

`select("Provider", ["claude-code", "codex", ...])` renders an inline list; the
user moves with ↑/↓ and confirms with Enter. Falls back to numbered text input
when stdin isn't a TTY or prompt_toolkit is unavailable.
"""

from __future__ import annotations

import sys

Option = "str | tuple[str, object]"


def _norm(options: list) -> tuple[list[str], list]:
    labels, values = [], []
    for o in options:
        if isinstance(o, tuple):
            labels.append(o[0])
            values.append(o[1])
        else:
            labels.append(str(o))
            values.append(o)
    return labels, values


def select(title: str, options: list, default=None):
    """Return the chosen value. Raises KeyboardInterrupt if cancelled."""
    labels, values = _norm(options)
    start = values.index(default) if default in values else 0

    if not sys.stdin.isatty():
        return _fallback(title, labels, values, start)
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.formatted_text import to_formatted_text
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
    except ImportError:
        return _fallback(title, labels, values, start)

    state = {"i": start}

    def render():
        frags = []
        for i, label in enumerate(labels):
            if i == state["i"]:
                frags.append(("class:sel", f" ❯ {label}\n"))
            else:
                frags.append(("", f"   {label}\n"))
        return to_formatted_text(frags)

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("c-p")
    def _(_e):
        state["i"] = (state["i"] - 1) % len(labels)

    @kb.add("down")
    @kb.add("c-n")
    def _(_e):
        state["i"] = (state["i"] + 1) % len(labels)

    @kb.add("enter")
    def _(e):
        e.app.exit(result=values[state["i"]])

    @kb.add("c-c")
    @kb.add("escape")
    def _(e):
        e.app.exit(result=_CANCEL)

    header = Window(FormattedTextControl(lambda: f"{title}"), height=1) if title else None
    body = Window(FormattedTextControl(render, focusable=True))
    root = HSplit([w for w in (header, body) if w is not None])
    app = Application(layout=Layout(root), key_bindings=kb, full_screen=False)
    result = app.run()
    if result is _CANCEL:
        raise KeyboardInterrupt
    return result


_CANCEL = object()


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
