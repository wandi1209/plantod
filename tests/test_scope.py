import subprocess

from plantod import scope


def test_is_allowed_patterns():
    assert scope.is_allowed("src/auth.py", ["src/*.py"], [])
    assert not scope.is_allowed("src/db.py", ["src/auth.py"], [])
    assert scope.is_allowed("anything", ["*"], [])
    assert not scope.is_allowed("secret.py", ["*"], ["secret.py"])  # forbidden wins
    assert not scope.is_allowed("x.py", [], [])                     # empty allowlist


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_enforce_reverts_out_of_scope(tmp_path):
    _git(tmp_path, "init")
    (tmp_path / "allowed.py").write_text("ok\n")
    (tmp_path / "sneaky.py").write_text("nope\n")

    report = scope.enforce(
        tmp_path,
        changed={"allowed.py", "sneaky.py"},
        allowed=["allowed.py"],
        forbidden=[],
    )
    assert "allowed.py" in report.in_scope
    assert "sneaky.py" in report.violations
    assert not report.clean
    # untracked out-of-scope file is deleted
    assert not (tmp_path / "sneaky.py").exists()
    assert (tmp_path / "allowed.py").exists()


def test_enforce_clean_when_all_allowed(tmp_path):
    _git(tmp_path, "init")
    (tmp_path / "a.py").write_text("x\n")
    report = scope.enforce(tmp_path, changed={"a.py"}, allowed=["*"], forbidden=[])
    assert report.clean
    assert (tmp_path / "a.py").exists()
