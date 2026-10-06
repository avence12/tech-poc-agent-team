# Agent-Assisted Technical Work Domain Context

## Glossary

### Individual Contributor (IC)

An individual contributor role. In this work context, an IC Technical Manager has no engineers reporting to them to whom engineering work can be delegated.

### Technical Survey (Tech Survey)

An early-stage investigation of technologies. In this work context, the subject areas include Web Applications and CCTV Edge AI, and the working method applies across projects.

### Proof of Concept (PoC)

A technical investigation that produces reproducible evidence sufficient to support an adoption or elimination decision. Evidence that a solution is unsuitable can be a successful outcome. A working backend or API is not a required deliverable.

### Decision Unit

A single technical question that can support a decision. The analysis, experiment execution, and independent challenge roles share the same approved question and evaluation criteria for this unit of work.

### Traceable Evidence

Information with identifiable sources that supports a technical comparison. A Technical Survey may draw conclusions from this evidence within the limits of what its sources establish.

### Experimental Evidence

Actual observations from a minimal experiment, accompanied by the conditions needed to reproduce them. Conclusions about technical integration bottlenecks require Experimental Evidence.

### Unknown

A technical claim for which the available evidence does not establish a conclusion.

### Agent A

The technical analysis role. Agent A analyzes existing architecture and potential impact, proposes research questions and evaluation criteria for the Human Technical Owner to approve, and corrects its analysis and assumptions when challenged. After Convergence, Agent A integrates evidence and challenges into a Decision Report draft. If the Round Limit is reached without Convergence, Agent A prepares an Escalation Summary.

### Agent B

The PoC and experiment execution role. Agent B produces reproducible experimental evidence, compares solution strengths and weaknesses, and corrects its experiments and evidence when challenged. Backend and API implementation are possible activities within this role.

### Agent C

The independent challenge role. Agent C produces test cases and review checklists, challenges the sufficiency of the technical evidence through Independent Challenge, and produces a Review Report for each Review Round.

### Independent Challenge

An assessment whose validation cases are derived from the approved question, evaluation criteria, and architecture facts before examining Agent B's results. Agent C conducts this assessment using an LLM model different from both the model used by Agent A and the model used by Agent B.

### Human Technical Owner

The individual contributor accountable for research questions, evaluation criteria, and the final technical conclusion. This role also owns task decomposition, acceptance criteria, conflict resolution, and final review.

### Decision Report

A report presenting technical evidence and conclusions to senior management to support a decision. It preserves unresolved challenges, evidence limitations, and recommended next steps. Agent A prepares the integrated draft, the Human Technical Owner is accountable for the technical conclusion, and senior management makes the decision informed by the report.

### Review Round

A unit of execution and assessment in which Agent B completes its work before Agent C reviews the results. The round ends with a Review Report.

### Review Report

A report produced by Agent C at the end of a Review Round. It identifies evidence gaps, problems, and required corrections, and supplies feedback for subsequent execution. Corrections to analysis and assumptions belong to Agent A; corrections to experiments and evidence belong to Agent B.

### Acceptance Blocker

An unresolved issue that prevents the evidence from meeting approved evaluation or acceptance criteria.

### Convergence

The state in which evidence is sufficient to answer the approved technical question and Agent C has no unresolved Acceptance Blockers.

### Round Limit

The maximum number of Review Rounds allowed for a Decision Unit. The agreed limit is three rounds, including the initial round and at most two subsequent rounds. Reaching the limit without Convergence stops further execution and requires a decision from the Human Technical Owner.

### Escalation Summary

Agent A's account of known facts, unknowns, blockers, and possible next steps when the Round Limit is reached without Convergence. It supports the Human Technical Owner's decision about further work and does not establish Convergence.

### Workflow Executor

The coordination role that starts the technical roles, hands off their reports, checks Convergence, and enforces the Round Limit. It preserves a separate Role Context for each technical role. It does not own research questions, approved criteria, or the final technical conclusion.

### Role Context

A technical role's own task history and working information. Each role maintains its own context and receives shared questions, criteria, facts, and reports relevant to its responsibility.

### Scope Change

A change to the approved research question, scope, or evaluation criteria. It requires approval from the Human Technical Owner. Corrections within the approved scope may proceed autonomously; disputed corrections are resolved by the Human Technical Owner.

### Lead Time

Elapsed time from formal handoff of a research topic to the Human Technical Owner's approval of its Decision Report.

### Human Review Time

The Human Technical Owner's total active time spent on a Decision Unit, including decomposition, evaluation and acceptance criteria, coordination, conflict resolution, review, and report revisions. The name covers all human work on the unit, rather than review alone.

### Major Rework

A substantial corrective cycle required because of an omission, an error, or failure to meet approved criteria. Each such cycle counts once. A valid negative experiment result alone is not Major Rework.

### Defect

A unique error first discovered during the Human Technical Owner's final review or within one week after approval of the Decision Report. Issues found by Agent C and corrected before final review are excluded.

### Baseline

Measurements from technical questions of comparable scope used to assess improvement. Where comparable measurements are unavailable, a Baseline must be established before claiming faster completion or unchanged human effort.
