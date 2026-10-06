#!/usr/bin/env python3
"""Offline Claude process boundary fixture. No production demo path."""
import json
import os
import sys
import uuid

args = sys.argv[1:]
def flag(name):
    return args[args.index(name) + 1] if name in args else None

request = json.load(sys.stdin)
role, phase, data = request["role"], request["phase"], request["input"]
scenario = os.environ.get("FAKE_SCENARIO", "pass")
if scenario == "bad_json" and phase == "review":
    print("not JSON")
    sys.exit(0)
if scenario == "report_error" and phase == "final":
    print(json.dumps({"is_error": True, "result": "service unavailable"}))
    sys.exit(1)
if scenario == "experiment_error" and phase == "experiment" and data["round"] == 2:
    print(json.dumps({"is_error": True, "result": "experiment session interrupted"}))
    sys.exit(1)
if scenario == "experiment_all_fail" and phase == "experiment":
    print(json.dumps({"is_error": True, "result": "infrastructure failure"}))
    sys.exit(1)
model = "claude-opus-test" if flag("--model") == "opus" else "claude-sonnet-test"
if scenario == "same_model" and role == "C":
    model = "claude-opus-test"
brief = data.get("brief", data)
criteria = brief.get("acceptance_criteria", [])
if phase == "analysis":
    out = {k: brief[k] for k in ("question", "scope", "acceptance_criteria", "architecture_facts")}
    out["report"] = "# Analysis\nA private recommendation; not a checklist input."
elif phase == "checklist":
    out = {"report": "# Independent checklist", "cases": [
        {"criterion_id": c["id"], "test": "measure it", "evidence_required": "reproducible observation"}
        for c in criteria]}
elif phase == "experiment":
    out = {"report": "# Experiment\nMeasured unsuitable performance.", "recommendation": "eliminate",
           "evidence": [{"criterion_id": c["id"], "observation": "threshold exceeded", "source": "experiment.log", "reproduce": "run approved command"} for c in criteria],
           "unknowns": [], "needs_human": False, "human_request": ""}
    if scenario == "pause_b" and data["round"] == 1:
        out.update(needs_human=True, human_request="approve additional resources")
elif phase == "review":
    number = data["round"]
    passed = scenario not in ("never", "a_fix", "pause", "retry", "experiment_error") or number >= 2
    if scenario == "never":
        passed = False
    if scenario == "human_rework" and number == 1 and data.get("human_resolution"):
        passed = False
    if scenario == "third_pass":
        passed = number == 3
    out = {"report": "# Review", "evidence_sufficient": passed,
           "decision_supported": "eliminate" if passed else "unknown",
           "acceptance_checks": [{"id": c["id"], "sufficient": passed, "evidence": "experiment.log"} for c in criteria],
           "blockers": [] if passed else ["missing measurement"],
           "corrections": {"A": ["correct architecture assumption"] if scenario == "a_fix" and not passed else [], "B": [] if passed else ["repeat measurement"]},
           "needs_human": scenario == "pause" and number == 1 and not data.get("human_resolution"),
           "human_request": "approve changed scope" if scenario == "pause" else "",
           "major_rework": not passed}
    if scenario == "missing_check":
        out["acceptance_checks"] = []
    if scenario == "bad_bool":
        out["evidence_sufficient"] = "false"
elif phase == "correction":
    out = {"report": "# Corrected architecture", "needs_human": False, "human_request": ""}
else:
    out = {"report": "# Decision report\nKnown, unknown, blockers, limits and next steps."}
session = flag("--resume") or str(uuid.uuid4())
usage = {model: {"inputTokens": 12, "outputTokens": 8}}
if scenario == "shared_helper":
    usage["claude-haiku-helper"] = {"inputTokens": 3, "outputTokens": 2}
if flag("--output-format") == "stream-json":
    print(json.dumps({"type": "system", "subtype": "init", "model": model, "session_id": session}))
    if scenario != "missing_primary":
        print(json.dumps({"type": "assistant", "parent_tool_use_id": None,
                          "message": {"model": model, "content": []}}))
    if scenario == "fallback_overlap" and role == "C":
        print(json.dumps({"type": "assistant", "parent_tool_use_id": None,
                          "message": {"model": "claude-opus-test", "content": []}}))
    print(json.dumps({"type": "assistant", "parent_tool_use_id": "helper-call",
                      "message": {"model": "claude-haiku-helper", "content": []}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "session_id": session, "structured_output": out,
                  "modelUsage": usage, "usage": {"input_tokens": 12}}))
