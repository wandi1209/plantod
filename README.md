# PLANTOD

**Plan, Task, Orchestrate, Deliver** — a planning-first, repo-aware AI coding orchestrator CLI.

PLANTOD turns a natural-language request ("add login feature") into a structured
workflow: **plan → tasks → scoped execution → test → handoff → escalation → final review**.
A strong model plans and reviews; a fast model executes small, scoped tasks. All
decisions and outputs are written to `.plantod/` in the repo so the work is auditable.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Prerequisites

- **Planner / reviewer** → Anthropic Claude: set `ANTHROPIC_API_KEY`.
- **Executor** → DeepSeek via [OpenCode](https://opencode.ai): install the `opencode` CLI and configure a model.
- **Offline / no keys**: set the drivers to `mock` in `.plantod/config.yaml`
  (`planner_driver`, `executor_driver`, `reviewer_driver`) to run the full flow deterministically.

## Usage

```bash
plantod init                       # detect repo, scaffold .plantod/
plantod plan "add login feature"   # plan + break into tasks + run the default flow
plantod plan "..." --yes --review  # approve gated tasks, run final review
plantod tasks                      # list tasks + status
plantod next                       # next runnable task
plantod run T001                   # run a single task
plantod review R001                # final review for a requirement
plantod status                     # board summary
plantod resume                     # where the last session left off
plantod                            # interactive chat-like session
```

## How it works

- **Adapters** (`plantod/adapters/`) make backends swappable: `claude`, `opencode`, `mock`.
- **State machine** (`plantod/schemas.py`) enforces legal task transitions
  (`pending → ready → in_progress → testing → done → reviewed`, plus `blocked → needs_planner_review`).
- **Approval gate** (`plantod/orchestrator.py`) auto-runs only low-risk, small-scope,
  testable tasks; everything else asks for approval.
- **Artifacts** (`.plantod/`): `requirements/ plans/ tasks/ handoffs/ reviews/ logs/`,
  markdown + YAML frontmatter; `board.json` / `session.json` for state.

## Configuration (`.plantod/config.yaml`)

| Key | Default | Meaning |
|-----|---------|---------|
| `planner` / `executor` / `reviewer` | claude-opus / deepseek-v4-flash / claude-opus | model names |
| `planner_driver` / `executor_driver` / `reviewer_driver` | claude / opencode / claude | backend (`claude` \| `opencode` \| `mock`) |
| `auto_run_small_tasks` | true | auto-run low-risk tasks |
| `require_approval_for_architecture` | true | gate high-risk changes |
| `test_before_done` | true | run tests before marking done |

## Development

```bash
pytest        # state machine, artifacts, config, full mock-adapter flow
```

Layout: `src/` package layout, entry point `plantod.cli:app`.

## License

MIT
