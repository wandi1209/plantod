"""Spec-per-task upgrade: planner spec flows to Task, executor prompt, task doc; AGENTS.md."""

from plantod.adapters.cliagent import CliAgent, _EXEC_PROMPT
from plantod.adapters.mock import MockAdapter
from plantod.repo import scan_repo
from plantod.schemas import Config, RoleBackend, Task
from plantod.state import StateManager
from plantod import orchestrator, cli


def _mock_state(tmp_path) -> StateManager:
    state = StateManager(tmp_path)
    m = RoleBackend(provider="mock")
    state.config = Config(planner=m, executor=m, reviewer=m, test_before_done=False, mode="auto")
    state.initialize()
    return state


def test_planner_spec_populates_task(tmp_path):
    state = _mock_state(tmp_path)
    orchestrator.run_request(state, "add login")
    tasks = list(state.board.tasks.values())
    assert tasks and all(t.spec.strip() for t in tasks)


def test_task_doc_renders_spec(tmp_path):
    state = _mock_state(tmp_path)
    orchestrator.run_request(state, "add login")
    doc = (state.artifact_dir / "tasks" / "T001.md").read_text()
    assert "## Spec" in doc


def test_exec_prompt_injects_spec():
    task = Task(id="T001", title="Landing", objective="build page",
               spec="Grid 12col, Inter font, shadcn buttons.",
               acceptance_criteria=["hero renders"], files_allowed=["index.html"])
    agent = CliAgent("claude-code")
    # build the same prompt execute() would send (without launching the CLI)
    prompt = _EXEC_PROMPT.format(
        id=task.id, title=task.title, objective=task.objective,
        spec=task.spec, guidance="", allowed=", ".join(task.files_allowed),
        forbidden="(none)", criteria="- hero renders",
    )
    assert "Grid 12col" in prompt
    assert "AGENTS.md" in prompt


def test_review_accepts_tasks(tmp_path):
    repo = scan_repo(tmp_path)
    task = Task(id="T001", title="x", objective="y", acceptance_criteria=["works"])
    res = MockAdapter().review("req", [], repo, [task])
    assert res.verdict == "approve"


def test_init_scaffolds_agents_md(tmp_path):
    cli._scaffold_conventions(tmp_path)
    agents = tmp_path / "AGENTS.md"
    assert agents.exists()
    assert "executor" in agents.read_text().lower()


def test_scaffold_skips_when_convention_exists(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("existing")
    cli._scaffold_conventions(tmp_path)
    assert not (tmp_path / "AGENTS.md").exists()
