from plantod import menu


def test_norm_str_and_tuple():
    labels, values = menu._norm(["a", ("Label B", 2)])
    assert labels == ["a", "Label B"]
    assert values == ["a", 2]


def test_fallback_default_on_empty(monkeypatch):
    # under pytest stdin.isatty() is False -> fallback path
    monkeypatch.setattr("builtins.input", lambda _p="": "")
    assert menu.select("pick", ["a", "b", "c"], default="b") == "b"


def test_fallback_numeric_choice(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _p="": "3")
    assert menu.select("pick", ["a", "b", "c"]) == "c"


def test_fallback_tuple_values(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _p="": "2")
    assert menu.select("pick", [("A", 1), ("B", 2)]) == 2


def test_fallback_bad_input_returns_default(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _p="": "nope")
    assert menu.select("pick", ["a", "b"], default="a") == "a"
