from plantod.artifacts import read_doc, read_json, scaffold, write_doc, write_json


def test_frontmatter_roundtrip(tmp_path):
    p = tmp_path / "tasks" / "T001.md"
    fm = {"id": "T001", "risk_level": "low", "tags": ["a", "b"]}
    write_doc(p, fm, "# Body\n\nhello")
    back_fm, body = read_doc(p)
    assert back_fm == fm
    assert "hello" in body


def test_read_doc_without_frontmatter(tmp_path):
    p = tmp_path / "plain.md"
    p.write_text("no frontmatter here", encoding="utf-8")
    fm, body = read_doc(p)
    assert fm == {}
    assert body == "no frontmatter here"


def test_json_roundtrip(tmp_path):
    p = tmp_path / "board.json"
    write_json(p, {"x": 1, "nested": {"y": [1, 2]}})
    assert read_json(p) == {"x": 1, "nested": {"y": [1, 2]}}
    assert read_json(tmp_path / "missing.json") == {}


def test_scaffold(tmp_path):
    scaffold(tmp_path / ".plantod")
    for sub in ("requirements", "plans", "tasks", "handoffs", "reviews", "logs"):
        assert (tmp_path / ".plantod" / sub).is_dir()
