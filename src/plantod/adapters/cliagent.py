"""Unified adapter that drives an agentic coding CLI headless.

Supported providers: claude-code (`claude -p`), codex (`codex exec`),
opencode (`opencode run`). One shape for all roles:

- plan / review / advise: the CLI answers; we parse a fenced ```json block.
- execute: the CLI edits the working tree; the executor enforces scope afterwards.

Backend-agnostic (PRD 14.1 / NFR-03).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..parsing import extract_json
from ..repo import RepoContext
from ..schemas import Handoff, Task
from .base import ExecResult, ModelAdapter, PlanResult, ReviewResult


@dataclass
class ProviderSpec:
    binary: str

    # build argv for a single non-interactive prompt.
    # `edit` = executor run that may modify files; read-only roles (plan/review)
    # pass edit=False so the CLI stays in a non-editing mode where available.
    def argv(self, prompt: str, model: str | None, edit: bool = False) -> list[str]:  # pragma: no cover
        raise NotImplementedError


class _ClaudeCode(ProviderSpec):
    def argv(self, prompt, model, edit=False):
        args = [self.binary, "-p", prompt]
        if model:
            args += ["--model", model]
        # executor needs to actually write files; read-only roles stay default
        args += ["--permission-mode", "acceptEdits" if edit else "plan"]
        return args


class _Codex(ProviderSpec):
    def argv(self, prompt, model, edit=False):
        args = [self.binary, "exec"]
        if model:
            args += ["--model", model]
        return args + [prompt]


class _OpenCode(ProviderSpec):
    def argv(self, prompt, model, edit=False):
        # opencode selects behavior via agents: `build` edits, `plan` is read-only
        args = [self.binary, "run", "--agent", "build" if edit else "plan"]
        if model:
            args += ["--model", model]
        return args + [prompt]


_SPECS: dict[str, ProviderSpec] = {
    "claude-code": _ClaudeCode(binary="claude"),
    "codex": _Codex(binary="codex"),
    "opencode": _OpenCode(binary="opencode"),
    # same binary as opencode; distinguished only by its model prefix/endpoint
    "opencode-go": _OpenCode(binary="opencode"),
}

_READONLY = "Do NOT modify, create, or delete any files. Only print the requested output."

_PLAN_PROMPT = """You are PLANTOD's PLANNER. A WEAK, fast model will execute your tasks — it cannot
make design or architecture decisions, only implement. So YOU must decide everything
and write a thick, self-contained implementation spec per task (a mini-PRD). The
executor should never have to invent anything; it just types out your spec.

Read the request and repo context, then produce a small, scoped, testable plan.
Break work into the fewest tasks that each touch a narrow file scope. {readonly}

For EACH task, the `spec` field is the most important output. Make it concrete and
prescriptive so a weak model produces work matching a strong model's quality:
- VISUAL/UI task: exact layout (grid, sections, order), spacing scale, color tokens
  (hex or named), typography (font, sizes, weights), component library to use and
  which blocks to copy, responsive/hover/empty states, and a named style reference
  (e.g. "clean SaaS like Linear/Stripe"). Never say "make it look nice" — specify it.
- LOGIC/BACKEND task: function/module contracts (signatures, inputs, outputs),
  data shapes, edge cases, error handling, and exactly what the tests must assert.
If the repo has AGENTS.md / CLAUDE.md conventions, tell the executor to follow them.

Respond with a short summary then ONE fenced ```json block matching exactly:
{{"title": str, "summary": str, "risk_level": "low|medium|high",
 "tasks": [{{"id": "T001", "title": str, "objective": str, "spec": str,
            "files_allowed": [str], "acceptance_criteria": [str],
            "test_command": str|null, "risk_level": "low|medium|high",
            "depends_on": [str]}}]}}
`spec` is a multi-paragraph string; `acceptance_criteria` are specific, checkable
statements a reviewer can verify one by one.

REQUEST:
{request}

REPO CONTEXT:
{repo}"""

_REVIEW_PROMPT = """You are PLANTOD's REVIEWER. A weak model did the editing, so do not trust that the
work is good — verify it. Check the actual repo state against EACH acceptance
criterion below, one at a time. A criterion is only met if you can confirm it in the
code. For UI, also judge whether the result matches the spec's stated design
(layout, tokens, components) — flag anything that looks off or generic.
{readonly}
Respond with a short summary then ONE fenced ```json block. Set verdict to "revise"
if ANY criterion fails; list each failing criterion as a finding "TXXX: <what fails>".
{{"verdict": "approve|revise", "summary": str, "findings": [str]}}

REQUEST:
{request}

ACCEPTANCE CRITERIA PER TASK (verify each against the repo):
{criteria}

HANDOFFS:
{handoffs}

REPO:
{repo}"""

_EXEC_PROMPT = """Task {id}: {title}
Objective: {objective}

IMPLEMENTATION SPEC — follow this exactly. Do not deviate, redesign, or "improve"
on it. All decisions are already made here; your job is only to implement them:
{spec}

If this repo has an AGENTS.md or CLAUDE.md, read it first and follow its conventions
(style, component library, tokens). Match the patterns of existing code around you.

{guidance}You MAY only edit these files: {allowed}
You MUST NOT edit: {forbidden}
Acceptance criteria (every one must hold when you finish):
{criteria}
Keep the change small and scoped. Do not refactor beyond the task.
If the spec is missing a decision you cannot make safely, or the task needs
architecture/cross-module changes, STOP and print 'ESCALATE: <reason>' instead of
guessing."""

_ADVISE_PROMPT = """You are PLANTOD's PLANNER unblocking an escalated task. {readonly}
Give concise, concrete guidance (2-5 sentences) so a fast executor can retry within
a narrow scope. Do not write code.

TASK {id}: {title}
OBJECTIVE: {objective}
ALLOWED FILES: {allowed}
BLOCK REASON: {reason}
REPO:
{repo}"""


class CliAgentError(RuntimeError):
    pass


class CliAgent(ModelAdapter):
    def __init__(self, provider: str, model: str | None = None, timeout_s: int = 900):
        if provider not in _SPECS:
            raise ValueError(f"unknown provider '{provider}'")
        self.name = provider
        self.spec = _SPECS[provider]
        self.model = model
        self.timeout_s = timeout_s

    @property
    def label(self) -> str:
        return f"{self.name} · {self.model}" if self.model else f"{self.name} (default model)"

    # -- subprocess -------------------------------------------------------- #
    def _run(self, prompt: str, root: Path, edit: bool = False) -> str:
        if shutil.which(self.spec.binary) is None:
            raise CliAgentError(
                f"'{self.spec.binary}' CLI not found on PATH for provider '{self.name}'. "
                f"Install it or run `plantod login` to pick another provider."
            )
        try:
            proc = subprocess.run(
                self.spec.argv(prompt, self.model, edit),
                cwd=root, capture_output=True, text=True, timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise CliAgentError(f"{self.name} timed out after {self.timeout_s}s") from e
        except OSError as e:
            raise CliAgentError(f"{self.name} failed to launch: {e}") from e
        if proc.returncode != 0:
            raise CliAgentError(self._friendly_error(proc.returncode, proc.stderr or ""))
        out = proc.stdout or ""
        from ..usage import estimate_tokens

        self.last_tokens_in = estimate_tokens(prompt)
        self.last_tokens_out = estimate_tokens(out)
        return out

    def _friendly_error(self, code: int, stderr: str) -> str:
        low = stderr.lower()
        if "insufficient balance" in low or "billing" in low or "quota" in low:
            return (f"{self.name}: provider account is out of credit/quota. Top up, or "
                    f"switch model/provider with `plantod login`.")
        if "unauthorized" in low or "authentication" in low or "not logged in" in low or "api key" in low:
            return (f"{self.name}: not authenticated. Log in to the provider CLI "
                    f"(e.g. `{self.spec.binary} auth login`), then retry.")
        if "rate limit" in low or "429" in low:
            return f"{self.name}: rate limited by the provider. Wait a moment and retry."
        return f"{self.name} exited {code}: {stderr[-200:].strip()}"

    # -- roles ------------------------------------------------------------- #
    def plan(self, request: str, repo: RepoContext) -> PlanResult:
        raw = self._run(_PLAN_PROMPT.format(readonly=_READONLY, request=request, repo=repo.summary()), repo.root)
        data = extract_json(raw)
        return PlanResult(
            title=data.get("title", request),
            summary=data.get("summary", ""),
            risk_level=data.get("risk_level", "medium"),
            tasks=data.get("tasks", []),
            raw=raw,
        )

    def execute(self, task: Task, repo: RepoContext) -> ExecResult:
        prompt = _EXEC_PROMPT.format(
            id=task.id, title=task.title, objective=task.objective,
            spec=task.spec.strip() or "(no detailed spec provided — implement the objective faithfully)",
            guidance=f"Planner guidance: {task.planner_guidance}\n" if task.planner_guidance else "",
            allowed=", ".join(task.files_allowed) or "(stay minimal)",
            forbidden=", ".join(task.files_forbidden) or "(none)",
            criteria="\n".join(f"- {c}" for c in task.acceptance_criteria),
        )
        try:
            raw = self._run(prompt, repo.root, edit=True)    # executor may modify files
        except CliAgentError as e:
            return ExecResult(escalate=True, escalate_reason=str(e), raw="")
        if "ESCALATE:" in raw:
            reason = raw.split("ESCALATE:", 1)[1].strip().splitlines()[0][:300]
            return ExecResult(escalate=True, escalate_reason=reason or "agent requested escalation", raw=raw)
        return ExecResult(summary=raw.strip()[-2000:], raw=raw)

    def review(self, request: str, handoffs: list[Handoff], repo: RepoContext,
               tasks: list[Task] | None = None) -> ReviewResult:
        hs = "\n\n".join(
            f"[{h.task_id}] {h.summary_of_changes}\ntests: {h.test_result}\nrisks: {h.risks_notes}"
            for h in handoffs
        ) or "(no handoffs)"
        criteria = "\n".join(
            f"{t.id} — {t.title}:\n" + "\n".join(f"  - {c}" for c in t.acceptance_criteria)
            for t in (tasks or []) if t.acceptance_criteria
        ) or "(none specified)"
        raw = self._run(
            _REVIEW_PROMPT.format(readonly=_READONLY, request=request, criteria=criteria,
                                  handoffs=hs, repo=repo.summary(30)),
            repo.root,
        )
        data = extract_json(raw)
        return ReviewResult(
            verdict=data.get("verdict", "approve"),
            summary=data.get("summary", ""),
            findings=data.get("findings", []),
            raw=raw,
        )

    def advise(self, task: Task, reason: str, repo: RepoContext) -> str:
        raw = self._run(
            _ADVISE_PROMPT.format(
                readonly=_READONLY, id=task.id, title=task.title, objective=task.objective,
                allowed=task.files_allowed, reason=reason, repo=repo.summary(30),
            ),
            repo.root,
        )
        return raw.strip()


def provider_binary(provider: str) -> str | None:
    """Binary name for a provider, or None for mock/unknown."""
    spec = _SPECS.get(provider)
    return spec.binary if spec else None


# Providers that can list models via `opencode models`, with the model-id prefix
# each one is restricted to (so opencode-go only shows opencode-go/* models).
_MODEL_LIST_PREFIX: dict[str, str] = {
    "opencode": "opencode/",
    "opencode-go": "opencode-go/",
    # claude-code / codex expose no reliable list command -> fall back to presets
}


def list_models(provider: str, timeout: int = 20) -> list[str]:
    """Query `opencode models`, filtered to the provider's own model prefix.

    Empty list on any failure. opencode-go returns only opencode-go/* models so a
    user on that account is never shown models they can't call.
    """
    prefix = _MODEL_LIST_PREFIX.get(provider)
    if prefix is None or shutil.which("opencode") is None:
        return []
    try:
        proc = subprocess.run(
            ["opencode", "models"], capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if proc.returncode != 0:
        return []
    seen, models = set(), []
    for line in proc.stdout.splitlines():
        m = line.strip()
        if m.startswith(prefix) and m not in seen:
            seen.add(m)
            models.append(m)
    return models
