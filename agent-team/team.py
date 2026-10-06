#!/usr/bin/env python3
"""Durable, human-gated A/B/C workflow. Python standard library only."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
from pathlib import Path
import sys

import claude_cli
from contracts import SCHEMAS, seconds, validate, validate_brief


def now():
    return dt.datetime.now(dt.timezone.utc)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(brief):
    return hashlib.sha256(json.dumps(brief, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Team:
    def __init__(self, directory):
        self.directory = directory
        self.state = read(directory / "state.json")

    def save(self):
        write(self.directory / "state.json", self.state)
        self.metrics()

    def metrics(self):
        state = self.state
        lead = None
        if "approved_at" in state:
            lead = (dt.datetime.fromisoformat(state["approved_at"]) - dt.datetime.fromisoformat(state["started_at"])).total_seconds()
        write(self.directory / "metrics.json", {
            "Lead Time": lead, "Human Review Time": state["human_seconds"],
            "Major Rework": state["rework_count"], "Defects": len(state["defects"])})

    def call(self, role, phase, payload):
        state = self.state
        state["calls"] += 1
        self.save()
        log = self.directory / "calls" / f"{state['calls']:03d}-{role}-{phase}"
        result = claude_cli.invoke(state, role, phase, payload, SCHEMAS[phase], log)
        output = result["output"]
        validate(output, SCHEMAS[phase])
        used = {r: set(state["actual_models"].get(r, [])) for r in "ABC"}
        used[role].update(result["models"])
        if used["C"] & (used["A"] | used["B"]):
            raise ValueError("C's actual model overlaps A/B; correct model configuration")
        for other, session in state["sessions"].items():
            if other != role and session == result["session_id"]:
                raise ValueError("Role session IDs overlap; contexts are not isolated")
        state["actual_models"] = {r: sorted(m) for r, m in used.items()}
        state["sessions"][role] = result["session_id"]
        state.pop("last_error", None)
        self.save()
        write(log.with_suffix(".output.json"), output)
        return output

    def prepare(self):
        if self.state["status"] != "new":
            raise ValueError("prepare requires a new decision unit")
        initial = self.state["initial_brief"]
        self.state["approved_brief"] = initial  # Permissions remain those of the human input.
        proposal = self.call("A", "analysis", initial)
        brief = dict(initial)
        brief.update({k: proposal[k] for k in ("question", "scope", "acceptance_criteria", "architecture_facts")})
        validate_brief(brief)
        write(self.directory / "approved-brief.json", brief)
        (self.directory / "analysis.md").write_text(proposal["report"], encoding="utf-8")
        self.state["status"] = "awaiting_approval"
        self.save()

    def approve(self):
        if self.state["status"] != "awaiting_approval":
            raise ValueError("approve requires an initial proposal awaiting human approval")
        self.freeze()
        self.state.update(status="approved", stage="checklist")
        self.save()

    def freeze(self):
        brief = read(self.directory / "approved-brief.json")
        validate_brief(brief)
        self.state["approved_brief"] = brief
        self.state["brief_hash"] = digest(brief)
        self.state["approvals"].append({"at": now().isoformat(), "brief": brief})

    def resolve(self, note):
        state = self.state
        if state["status"] not in ("needs_human", "approved", "running", "report_ready"):
            raise ValueError("resolve requires a paused or approved unfinished unit")
        if not note.strip():
            raise ValueError("A human resolution note is required")
        previous = state["brief_hash"]
        self.freeze()
        state["human_resolution"] = note
        if state["brief_hash"] != previous:
            if len(state["rounds"]) >= 3:
                raise ValueError("Three attempts used; start a new decision unit for changed scope")
            state["sessions"].pop("C", None)
            state.pop("checklist", None)
            state["stage"] = "checklist"
        elif state["stage"] in ("review", "after_review", "final"):
            state["stage"] = "review"  # Reassess existing evidence against the human ruling.
        elif state["stage"] == "correct_A":
            state["stage"] = "correct_A"
        state["status"] = "approved"
        self.save()

    def require_approved(self):
        state = self.state
        if state["status"] not in ("approved", "running"):
            raise ValueError(f"run requires human-approved work; status={state['status']}")
        self.require_frozen_brief()

    def require_frozen_brief(self):
        if digest(read(self.directory / "approved-brief.json")) != self.state["brief_hash"]:
            raise ValueError("Approved brief changed; use resolve with an explicit human ruling")

    def coverage(self, output, phase):
        wanted = {c["id"] for c in self.state["approved_brief"]["acceptance_criteria"]}
        key, id_key = ("cases", "criterion_id") if phase == "checklist" else ("acceptance_checks", "id")
        ids = [item[id_key] for item in output[key]]
        if set(ids) != wanted or (phase == "review" and len(ids) != len(wanted)):
            raise ValueError(f"{phase}: every approved criterion must be covered; no extra criteria")

    def converged(self, review):
        return (review["evidence_sufficient"] and review["decision_supported"] != "unknown"
                and all(c["sufficient"] and c["evidence"].strip() for c in review["acceptance_checks"])
                and not review["blockers"] and not review["needs_human"])

    def pause(self, output):
        self.state["status"] = "needs_human"
        self.state["human_request"] = output["human_request"]
        self.save()

    def run(self):
        self.require_approved()
        state = self.state
        state["status"] = "running"
        self.save()
        while True:
            stage = state["stage"]
            brief = state["approved_brief"]
            rounds = state["rounds"]
            payload = {"brief": brief}
            if stage == "checklist":
                output = self.call("C", "checklist", payload)
                self.coverage(output, "checklist")
                state["checklist"] = output
                state["stage"] = "execute"
                write(self.directory / "checklist.json", output)
            elif stage == "execute":
                if len(rounds) >= 3:
                    state["stage"] = "escalation"
                    self.save()
                    continue
                feedback = next((r["C"] for r in reversed(rounds) if "C" in r), None)
                rounds.append({"number": len(rounds) + 1})  # Reserve before launching B.
                self.save()
                payload.update(round=len(rounds), checklist=state["checklist"], feedback=feedback,
                               analysis_correction=state.get("analysis_correction"),
                               human_resolution=state.get("human_resolution"))
                output = self.call("B", "experiment", payload)
                rounds[-1]["B"] = output
                if feedback and feedback["major_rework"]:
                    state["rework_count"] += 1
                state["stage"] = "review"
                if output["needs_human"]:
                    self.pause(output)
                else:
                    self.save()
                write(self.directory / f"round-{len(rounds)}-experiment.json", output)
                if output["needs_human"]:
                    return
            elif stage == "review":
                payload.update(round=len(rounds), checklist=state["checklist"], experiment=rounds[-1]["B"],
                               analysis_correction=state.get("analysis_correction"),
                               human_resolution=state.get("human_resolution"))
                output = self.call("C", "review", payload)
                self.coverage(output, "review")
                rounds[-1]["C"] = output
                state["stage"] = "after_review"
                if output["needs_human"]:
                    self.pause(output)
                else:
                    self.save()
                write(self.directory / f"round-{len(rounds)}-review.json", output)
                (self.directory / f"round-{len(rounds)}-review.md").write_text(output["report"], encoding="utf-8")
                if output["needs_human"]:
                    return
            elif stage == "after_review":
                review = rounds[-1]["C"]
                if self.converged(review):
                    state["stage"] = "final"
                elif len(rounds) >= 3:
                    state["stage"] = "escalation"
                elif review["corrections"]["A"]:
                    state["stage"] = "correct_A"
                else:
                    state["stage"] = "execute"
            elif stage == "correct_A":
                payload.update(review=rounds[-1]["C"], human_resolution=state.get("human_resolution"))
                output = self.call("A", "correction", payload)
                state["analysis_correction"] = output
                rounds[-1]["A"] = output
                if output["needs_human"]:
                    self.pause(output)
                    return
                state["stage"] = "execute"
            elif stage in ("final", "escalation"):
                payload.update(rounds=rounds, analysis_correction=state.get("analysis_correction"),
                               human_resolution=state.get("human_resolution"))
                output = self.call("A", stage, payload)
                filename = "decision-report.md" if stage == "final" else "escalation-report.md"
                heading = "# INCONCLUSIVE — three-round limit reached\n\n" if stage == "escalation" else ""
                (self.directory / filename).write_text(heading + output["report"], encoding="utf-8")
                state["status"] = "report_ready" if stage == "final" else "escalated"
                self.save()
                return
            else:
                raise ValueError(f"Unknown stage: {stage}")
            self.save()

    def human_stop(self):
        started = self.state.pop("human_started_at", None)
        if not started:
            raise ValueError("Human timer is not running")
        self.state["human_seconds"] += max(0, (now() - dt.datetime.fromisoformat(started)).total_seconds())
        self.state["human_recorded"] = True

    def finish(self, args):
        state = self.state
        if state["status"] not in ("report_ready", "escalated"):
            raise ValueError("A completed report is required for final human approval")
        self.require_frozen_brief()
        if state["status"] == "escalated" and not args.inconclusive:
            raise ValueError("Escalation needs explicit --inconclusive approval; it is not convergence")
        if "human_started_at" in state:
            self.human_stop()
        if args.human_seconds is not None:
            state["human_seconds"] = seconds(args.human_seconds)
            state["human_recorded"] = True
        if not state["human_recorded"]:
            raise ValueError("Record human effort or supply --human-seconds before final approval")
        if args.major_rework is not None:
            if args.major_rework < 0:
                raise ValueError("Major Rework must be nonnegative")
            state["rework_count"] = args.major_rework
        state["outcome"] = "inconclusive" if state["status"] == "escalated" else "converged"
        state["approved_at"] = now().isoformat()
        state["status"] = "approved_report"
        self.save()


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    names = ["init", "prepare", "approve", "run", "resolve", "status", "human-start",
             "human-stop", "human-add", "finish", "defect", "finalize"]
    commands = {}
    for name in names:
        commands[name] = sub.add_parser(name)
        commands[name].add_argument("--run", type=Path, required=True)
    init = commands["init"]
    init.add_argument("--brief", type=Path, required=True)
    init.add_argument("--workspace", type=Path, required=True)
    init.add_argument("--claude-bin", default="claude")
    for role, model in (("a", "opus"), ("b", "opus"), ("c", "sonnet")):
        init.add_argument(f"--model-{role}", default=model)
    commands["resolve"].add_argument("--note", required=True)
    commands["human-add"].add_argument("--seconds", type=float, required=True)
    commands["finish"].add_argument("--human-seconds", type=float)
    commands["finish"].add_argument("--major-rework", type=int)
    commands["finish"].add_argument("--inconclusive", action="store_true")
    commands["defect"].add_argument("--id", required=True)
    commands["defect"].add_argument("--note", required=True)
    return root


def operate(args):
    directory = args.run.resolve()
    if args.command == "init":
        if (directory / "state.json").exists():
            raise ValueError("Decision unit already exists")
        brief = read(args.brief)
        validate_brief(brief)
        workspace = args.workspace.resolve()
        if not workspace.is_dir():
            raise ValueError("Workspace must be an existing directory")
        models = {r: getattr(args, f"model_{r.lower()}").strip() for r in "ABC"}
        if not all(models.values()) or models["C"] in (models["A"], models["B"]):
            raise ValueError("C must use a different configured model from A/B")
        directory.mkdir(parents=True, exist_ok=True)
        write(directory / "state.json", {"status": "new", "started_at": now().isoformat(),
              "workspace": str(workspace), "claude_bin": args.claude_bin, "models": models,
              "initial_brief": brief, "rounds": [], "sessions": {}, "actual_models": {},
              "approvals": [], "calls": 0, "human_seconds": 0, "human_recorded": False,
              "rework_count": 0, "defects": {}})
    team = Team(directory)
    state = team.state
    command = args.command
    if command == "status":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return
    if state["status"] == "finalized":
        raise ValueError("Finalized metrics are immutable")
    try:
        if command == "prepare":
            team.prepare()
        elif command == "approve":
            team.approve()
        elif command == "run":
            team.run()
        elif command == "resolve":
            team.resolve(args.note)
        elif command == "human-start":
            if "human_started_at" in state:
                raise ValueError("Human timer already running")
            state["human_started_at"] = now().isoformat()
        elif command == "human-stop":
            team.human_stop()
        elif command == "human-add":
            state["human_seconds"] += seconds(args.seconds)
            state["human_recorded"] = True
        elif command == "finish":
            team.finish(args)
        elif command == "defect":
            if state["status"] not in ("report_ready", "escalated", "approved_report"):
                raise ValueError("Defects are recorded at final review or after approval")
            if "approved_at" in state and now() > dt.datetime.fromisoformat(state["approved_at"]) + dt.timedelta(days=7):
                raise ValueError("Defect observation window has ended")
            if not args.id.strip() or not args.note.strip():
                raise ValueError("A unique defect ID and description are required")
            state["defects"].setdefault(args.id.strip(), {"note": args.note, "found_at": now().isoformat()})
        elif command == "finalize":
            if state["status"] != "approved_report":
                raise ValueError("Human report approval is required")
            if now() < dt.datetime.fromisoformat(state["approved_at"]) + dt.timedelta(days=7):
                raise ValueError("Wait until the seven-day defect window ends")
            if "human_started_at" in state:
                team.human_stop()
            state["status"] = "finalized"
        team.save()
    except (ValueError, OSError) as error:
        # Only calls/run checkpoints commit workflow mutations; invalid operator input is not approval.
        persisted = Team(directory)
        persisted.state["last_error"] = str(error)
        persisted.save()
        raise
    print(f"status={state['status']} rounds={len(state['rounds'])}/3 run={directory}")


def main():
    args = parser().parse_args()
    directory = args.run.resolve()
    if args.command != "init" and not (directory / "state.json").exists():
        raise ValueError("Initialize the decision unit first")
    directory.mkdir(parents=True, exist_ok=True)
    # One writer per unit, including while a Claude call is active; status reads are atomic.
    with (directory / ".lock").open("a") as lock:
        if args.command != "status":
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError("Another command is active for this decision unit") from error
        operate(args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
