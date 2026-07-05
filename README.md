# PLANTOD

[![PyPI version](https://img.shields.io/pypi/v/plantod.svg)](https://pypi.org/project/plantod/)
[![Python versions](https://img.shields.io/pypi/pyversions/plantod.svg)](https://pypi.org/project/plantod/)
[![CI](https://github.com/wandi1209/plantod/actions/workflows/ci.yml/badge.svg)](https://github.com/wandi1209/plantod/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Plan, Task, Orchestrate, Deliver** — a planning-first, repo-aware AI coding orchestrator CLI.

PLANTOD turns a natural-language request ("add login feature") into a structured
workflow: **plan → tasks → scoped execution → test → handoff → escalation → final review**.
A strong model plans and reviews; a fast model executes small, scoped tasks. All
decisions and outputs are written to `.plantod/` in the repo so the work is auditable.

## Install

```bash
pip install plantod
# or, isolated global CLI:
pipx install plantod
```

Requires Python 3.11+. Then configure your providers with `plantod login`.

<details>
<summary>From source (development)</summary>

```bash
git clone https://github.com/wandi1209/plantod && cd plantod
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
</details>

## Providers

PLANTOD drives **agentic coding CLIs** as its backends — one per role. Install the
CLI(s) for the providers you pick; each handles its own auth/model config.

| Provider | Binary | Invocation |
|----------|--------|-----------|
| `claude-code` | `claude` | `claude -p "<prompt>"` |
| `codex` | `codex` | `codex exec "<prompt>"` |
| `opencode` | `opencode` | `opencode run "<prompt>"` |

### `plantod login`

Set the provider + model for each role (planner / executor / reviewer):

```bash
plantod login                                             # arrow-key wizard (provider + model per role)
plantod login --role executor --provider codex --model o4 # non-interactive, one role
plantod login --role planner  --provider claude-code      # model optional -> provider default
plantod login ... --project                               # save to THIS repo instead of global
```

The wizard is an inline **arrow-key menu** (↑/↓ + Enter, type to filter): pick a
provider, then a model. Where the provider CLI can list its models (e.g.
`opencode models`), PLANTOD **fetches the live list** so you never type an id by
hand — otherwise it offers a shortlist plus `(default)` / `custom…`. `plantod mode`
with no argument is selectable the same way.

Config precedence (low → high): **defaults < global (`~/.config/plantod/config.yaml`) < project (`.plantod/config.yaml`)**.
`login` writes the global scope by default so settings carry across repos (NFR-02);
`--project` overrides for one repo. `plantod init` inherits the global defaults.

### Run mode

```bash
plantod mode              # show current mode
plantod mode auto         # unattended: plan, execute, and review to done, no prompts
plantod mode approval     # default: gate risky/wide-scope tasks for your approval
plantod mode auto --project   # set for this repo only
```

- **approval** (default) — small, low-risk, testable tasks auto-run; anything risky
  or wide-scope waits for your yes/no.
- **auto** — every task runs unattended through execution and final review. The
  scope guard and escalation loop still apply, so out-of-scope edits are reverted
  and blocked tasks are re-planned automatically.

## Prerequisites

- Install the CLI for each provider you configure (see table above); each tool
  manages its own authentication.
- `.env` in the repo root is auto-loaded into the environment (see `.env.example`)
  for any provider that reads env vars.
- A **git repo** is required for the scope guard — run `plantod init` inside one.

## Usage

```bash
plantod login                      # pick provider + model per role (see Providers)
plantod init                       # detect repo, scaffold .plantod/ (inherits global)
plantod plan "add login feature"   # plan + break into tasks + run the default flow
plantod plan "..." --yes --review  # approve gated tasks, run final review
plantod tasks                      # list tasks + status
plantod next                       # next runnable task
plantod run T001                   # run a single task
plantod review R001                # final review for a requirement
plantod status                     # board summary
plantod resume                     # where the last session left off
plantod                            # interactive chat session (see below)
plantod usage                      # estimated token usage / cost
```

### Interactive session

Run bare `plantod` for a Claude-Code-style chat: an inline REPL with scrollback,
arrow-key history, ctrl-r search, slash-command autocomplete, and **multi-turn
memory** — follow-ups keep context, so after "add login" you can say "now add
logout too" and the planner understands the thread.

```
plantod › add a health-check endpoint
plantod › now add a test for it        # remembers the previous turn
plantod › /tasks                       # slash commands for everything
```

Slash commands: `/help /login /mode /status /tasks /usage /review <RID> /resume /clear /quit`.
First run offers to `init` for you and checks your provider CLIs are installed.
Conversation persists in `.plantod/session.json` (last 40 turns); `/clear` resets it.

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

> **Honest caveat:** the table above is an illustrative model, not a benchmark.
> PLANTOD *does* meter usage, but as an **estimate** — provider CLIs run headless
> and don't reliably report token counts, so figures are derived from text length
> (~4 chars/token). Good for relative comparison, not billing. The structural saving
> (route bulk edits to a cheap model, keep reasoning on a strong one) holds regardless.

### Seeing your own numbers

Every run prints an estimated token line, and `plantod usage` shows the breakdown:

```
$ plantod usage
         Estimated usage (heuristic)
 Provider   Calls   Tokens in   Tokens out
 opencode       4      12,400        8,900
 claude-code    2       3,100        1,200
 Total ~ 25,600 tokens ~ $0.42
```

Add a `prices` table to your config to get the cost estimate (USD per 1M tokens,
`[input, output]` per provider):

```yaml
prices:
  claude-code: [15, 75]
  opencode: [0.3, 0.9]
```

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
| `planner` / `executor` / `reviewer` | `{provider, model}` per role | backend for each role — set via `plantod login` |
| default providers | claude-code / opencode / claude-code | planner / executor / reviewer |
| `mode` | approval | `approval` (gate risky) or `auto` (unattended to done) |
| `auto_run_small_tasks` | true | auto-run low-risk tasks (approval mode) |
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
