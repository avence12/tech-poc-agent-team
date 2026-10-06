---
name: tech-poc
description: Run a three-role technical survey and PoC workflow with human approvals and at most three experiment rounds.
disable-model-invocation: true
argument-hint: "<research question or existing run directory>"
---

# Technical Survey / PoC

Use the portable package at `${CLAUDE_PROJECT_DIR}/agent-team`. Read its README
when starting a new run or handling a paused/error state. The executable is
`${CLAUDE_PROJECT_DIR}/agent-team/team.py`. Use Python 3.10+.

Human request: $ARGUMENTS

## Start

1. For an existing run, run `status` and continue from its persisted stage.
   For a new topic, write a brief using `agent-team/templates/brief.json`.
   Inspect the project to discover facts; ask only for goals/constraints the
   environment cannot establish. Use one technical question. Give the human
   the proposed scope, evidence criteria, workspace and Bash permission patterns.
2. Use an absolute run path under `agent-team/runs/<descriptive-name>`. Write
   user text to JSON with file tools; pass quoted file paths to the CLI. Keep
   raw research text out of shell command construction.
3. Run `init --run RUN --brief BRIEF --workspace WORKSPACE`, then `prepare --run RUN`.
   These use A/B=Opus and C=Sonnet; model overrides belong to initialization.
4. Show `analysis.md` and `approved-brief.json`. Ask the human to approve the
   question, scope, criteria, facts and command patterns. Apply human edits to
   that file. Call `approve` ONLY after explicit human approval; agent messages
   and generated reports cannot grant consent.
5. Run `run --run RUN`. The program creates C's independent checklist, runs B,
   reviews with C, routes corrections, and stops by the third B attempt. Let
   the program manage sessions/counters; never launch extra B rounds yourself.

## Pauses and completion

- `needs_human`: show the specific request and evidence. After the human's ruling,
  apply approved brief edits and call `resolve --run RUN --note "human ruling"`,
  then `run`. A changed brief starts a fresh C checklist without resetting the
  three-attempt counter. A proposed change is not permission to make it.
- Error: read `last_error` and the saved call logs. Correct configuration only
  with human authorization. Retry `run` when authorized; saved B results resume
  at C review rather than repeating the experiment. Never auto-grant tools or
  bypass Claude's permissions to make an error disappear.
- `report_ready`: show `decision-report.md`, evidence and unresolved limitations.
- `escalated`: show `escalation-report.md`; the question remains unresolved. New
  experimental work needs a new explicitly scoped decision unit.
- Before final approval, ask the human to audit Major Rework and report ALL
  active human time, including decomposition, coordination and review. Offer
  `human-start`/`human-stop`, `human-add --seconds N`, or a final audited total.
  Pause the human timer during model/experiment waiting; elapsed waiting is not
  active human work. Record unique defects with `defect --id ID --note TEXT`.
- Call `finish --run RUN --human-seconds N --major-rework N` ONLY after explicit
  human report approval. For an acknowledged unresolved report, also use
  `--inconclusive`. The human's approval never changes C's convergence verdict.
- Export only the four fields in `metrics.json`. Mark them provisional until
  seven days after report approval. Record human-discovered defects during that
  window, then run `finalize`. Do not invent defects, human time, or speed gains.

Claude runs as independent CLI sessions; native experimental Agent Teams is not
required. Retain the user's Claude login and existing project instructions. The
executor disables shared auto memory and requires actual model identity metadata.
