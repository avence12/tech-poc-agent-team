# Technical Survey / PoC Agent Team

Approved in the design interview; implementation authorized on 2026-10-05.

- One decision unit is one technical question, shared by A/B/C.
- A/B default to Opus; C defaults to Sonnet. C's actual model must differ from A/B.
- A proposes analysis, question, criteria and architecture facts. Human approval freezes the brief before experiments.
- C builds its checklist from the approved brief before receiving B results. Each role has its own Claude session; shared auto memory is disabled.
- B produces reproducible evidence; C reviews only after B completes. C owns each round's review report. A fixes analysis; B fixes experiments. Scope/criteria changes and disputes pause for human approval.
- At most three B execution attempts, including the first. Resume a pending C review without repeating B. A failed/interrupted B attempt consumes its reserved slot.
- Stop on sufficient evidence for adoption or elimination, complete criterion coverage and no acceptance blockers. Negative experimental results can be successful evidence.
- After convergence, A drafts the management decision report. After three unsuccessful attempts, A produces an explicitly inconclusive escalation report. Human final approval is always required.
- Lead Time: formal handoff to human report approval, including waiting/rework. Human Review Time: all active human effort. Major Rework: executed substantial corrective cycles; C flags, human audits. Defects: unique issues first found at final review or within seven days after approval; repaired C findings are excluded.
- Only four numeric performance fields are exported, in seconds/counts. Token usage stays in CLI diagnostics. Defects remain provisional until the seven-day observation window ends.
- Comparative improvement needs comparable scope and a baseline; this tool does not claim speed gains automatically.

## Delivery

Python standard-library CLI, three role prompts, brief/review/decision templates,
a `/tech-poc` Claude Code skill, and offline executable tests. No global Claude
settings, dependencies, or existing application files are changed.

Commands preserve state between Claude Code Bash calls; approval is an explicit
operator command, never inferred from a model response. `dontAsk` permissions
allow approved tools/command patterns and fail closed on requests needing consent.
The workspace's Claude customizations remain active; the target workspace must be
one the operator trusts. Approved Bash patterns are permissions, not OS isolation.

## Verification

Offline tests use a fake Claude executable at the process boundary. They verify
handoffs, isolated contexts, model identity, first-round negative success, three
rounds, A correction routing, approvals, restart checkpoints, invalid CLI output,
metric counts, and the seven-day defect window. Live LLM calls require a real
research brief and are not part of installation verification.
