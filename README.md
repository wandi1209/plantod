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

- **Planner / reviewer** → Anthropic Claude: set `ANTHROPIC_API_KEY` (or put it in `.env`, auto-loaded — see `.env.example`).
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

## Why planning-first saves tokens (cost model)

PLANTOD's economics come from **routing**: a strong, expensive model only *plans*
and *reviews* (low token volume, high-value reasoning), while a cheap, fast model
does the *bulk editing* (high token volume, low-level work). Most tokens in a coding
task are spent reading context and writing edits — so you want those on the cheap model.

**Illustrative example** — one feature = 1 plan + 4 tasks + 1 review. Token splits
below are *assumptions to show the shape of the saving*, not measurements:

| Stage | Tokens | All-in-one (strong model) | PLANTOD (routed) |
|-------|-------:|--------------------------:|-----------------:|
| Plan + review | ~30K | strong | strong |
| Task execution (×4) | ~200K | strong | **cheap executor** |
| **Total billed as** | ~230K | 230K × strong-rate | 30K × strong-rate + 200K × cheap-rate |

If the executor model is ~15× cheaper per token than the planner (a typical
fast-model vs frontier-model gap), the routed run costs roughly:

```
strong_share = 30K
cheap_share  = 200K / 15  ≈ 13.3K  strong-equivalent tokens
routed_total ≈ 43.3K  vs  230K   →  ~5× cheaper for this mix
```

The exact multiple depends on your models and the plan/execution token ratio —
plug in current per-token prices for your planner and executor to get real numbers.

> **Honest caveat:** these figures are an illustrative model, not a benchmark.
> PLANTOD does not yet meter real token usage — **cost tracking is on the v2
> roadmap** (PRD §27). The structural saving (route bulk edits to a cheap model,
> keep reasoning on a strong one) holds regardless; the exact ratio is yours to measure.

Beyond cost, the planning-first flow also reduces *wasted* tokens: scoped tasks and
the scope guard stop the executor from sprawling across the repo and re-generating
work, which is where "just let the big model code" runs burn tokens on churn.

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
| `enforce_scope` | true | revert executor edits outside `files_allowed` |
| `apply_requires_approval` | false | confirm the in-scope diff before keeping it |
| `exec_timeout_s` / `test_timeout_s` | 900 / 600 | subprocess timeouts |
| `max_retries` | 3 | retry transient backend failures / cap replans |
| `auto_replan_on_escalation` | true | planner advises + retries an escalated task |

## Production notes

- **Scope guard** — after each executor run, any file changed outside the task's
  `files_allowed` (or matching `files_forbidden`) is reverted via git and the task
  is escalated. This is enforced, not just prompted.
- **State safety** — `board.json` / `session.json` and all artifacts are written
  atomically (temp file + rename). A per-project advisory lock (`.plantod/.lock`)
  stops concurrent runs from corrupting state.
- **Escalation loop** — a blocked task goes `needs_planner_review`; the planner
  produces guidance and the task retries with narrower scope, capped by `max_retries`.
- **Resilience** — backend calls retry with exponential backoff; subprocesses have
  timeouts; malformed model JSON is parsed defensively.
- Requires a **git repo** for the scope guard; run `plantod init` inside one.

## Development

```bash
pytest        # state machine, artifacts, config, full mock-adapter flow
```

Layout: `src/` package layout, entry point `plantod.cli:app`.

## License

MIT
