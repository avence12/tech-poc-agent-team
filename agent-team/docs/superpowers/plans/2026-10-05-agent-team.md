# Agent Team Implementation Plan

> **For agentic workers:** Execute inline following the user's instruction to begin implementation. Steps use checkbox syntax for tracking.

**Goal:** Deliver an executable Claude Code workflow for technical survey and PoC with A/B/C, a hard three-round limit, human gates and four metrics.

**Architecture:** A Python CLI persists approved inputs, role sessions, round outputs and metrics. A separate Claude adapter invokes CLI sessions with validated structured output. A Claude Code skill drives commands across human approval pauses.

**Tech Stack:** Python 3.10+ standard library, Claude Code CLI (verified locally: 2.1.233).

**Spec:** `agent-team/DESIGN.md`; glossary: `agent-team/CONTEXT.md`.

## Global Constraints

- A/B: `opus`; C: `sonnet`; models configurable when initializing a decision unit.
- Three execution attempts maximum, including the first; no automatic human approvals.
- Role contexts isolated; C checklist exists before B results are supplied.
- Formal metrics: Lead Time / Human Review Time / Major Rework / Defects only.
- Preserve existing CONTEXT.md and manager-cockpit; no global configuration or Git operations.

## Review Focus

- Provider/model overrides: verify returned actual model metadata, not only configured aliases.
- Invalid/missing criterion checks: reject reports instead of assuming convergence.
- Interrupted execution: saved B outputs must not be rerun when C or A fails.
- Scope changes: no silent changes or counter resets; renewed checklist uses a fresh C context.
- Observation window: provisional defects cannot be finalized early; duplicate IDs count once.

### Task 1: Executable workflow and Claude adapter

**Files:** `team.py`, `claude_cli.py`, `contracts.py`, `roles/*.md`, `tests/test_team.py`, `tests/fake_claude.py`.

**Interfaces:** `team.py <command> --run PATH`; adapter `invoke(state, role, phase, payload, schema, log_path) -> {output, session_id, models}`; contracts expose schemas and `validate`.

- [x] Write CLI tests proving initialization, initial approval, independent checklist and convergence/three-round outcomes.
- [x] Run tests and observe nonzero missing-executor failure.
- [x] Implement durable checkpoints, strict contracts and actual CLI invocation with isolated role sessions.
- [x] Verify all workflow, model mismatch, pause and interruption tests pass.

### Task 2: Human metrics and report approval

**Files:** `team.py`, `tests/test_team.py`.

**Interfaces:** `human-start`, `human-stop`, `human-add`, `finish`, `defect`, `finalize`; `metrics.json` contains exactly the four named numeric fields after approval.

- [x] Write failing tests for timing, rework auditing, deduplication and seven-day finalization.
- [x] Implement metric recording and explicit final approval, including acknowledged inconclusive outcomes.
- [x] Verify the entire offline suite passes.

### Task 3: Claude Code entrypoint and operating package

**Files:** `.claude/skills/tech-poc/SKILL.md`, `templates/*`, `README.md`, `.gitignore` scoped to agent-team.

- [x] Provide the invocation steps, human gates, cross-project installation instructions and report templates.
- [x] Exercise the documented commands with the fake CLI, without LLM requests.
- [x] Run the full test suite, compile Python, inspect scope and obtain a fresh independent code review.

Completion evidence and review fixes: `agent-team/docs/progress.md`. Live research validation is deferred to the first human-approved technical question; offline tests used no LLM requests.
