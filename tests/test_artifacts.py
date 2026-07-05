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


def test_frontmatter_value_containing_dashes(tmp_path):
    # a model summary with a literal '---' line must not truncate the parse
    p = tmp_path / "h.md"
    summary = "Let me check the images\n---\nthen build the layout"
    write_doc(p, {"task_id": "T003", "summary_of_changes": summary}, "# body\n---\nmore")
    fm, body = read_doc(p)
    assert fm["task_id"] == "T003"
    assert fm["summary_of_changes"] == summary
    assert "more" in body


def test_read_doc_malformed_frontmatter_is_tolerant(tmp_path):
    # unterminated quote in frontmatter -> return {} + full text, never raise
    p = tmp_path / "bad.md"
    p.write_text("---\nsummary: 'unterminated\nstill going\n---\nbody\n", encoding="utf-8")
    fm, body = read_doc(p)
    assert fm == {}
    assert "unterminated" in body


def test_json_roundtrip(tmp_path):
    p = tmp_path / "board.json"
    write_json(p, {"x": 1, "nested": {"y": [1, 2]}})
    assert read_json(p) == {"x": 1, "nested": {"y": [1, 2]}}
    assert read_json(tmp_path / "missing.json") == {}


def test_scaffold(tmp_path):
    scaffold(tmp_path / ".plantod")
    for sub in ("requirements", "plans", "tasks", "handoffs", "reviews", "logs"):
        assert (tmp_path / ".plantod" / sub).is_dir()
