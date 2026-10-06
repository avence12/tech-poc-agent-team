import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TEAM = ROOT / "team.py"
FAKE = ROOT / "tests/fake_claude.py"
sys.path.insert(0, str(ROOT))
import team


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.run = self.base / "run"
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        FAKE.chmod(0o755)
        self.brief = self.base / "brief.json"
        self.brief.write_text(json.dumps({
            "question": "Can X integrate with Y?", "scope": "one integration",
            "acceptance_criteria": [{"id": "AC1", "description": "Measure latency and decide against threshold"}],
            "constraints": [], "architecture_facts": [{"fact": "Y exists", "source": "README"}],
            "allowed_commands": []}), encoding="utf-8")
        self.scenario = "pass"

    def command(self, command, *args, ok=True):
        env = dict(os.environ, FAKE_SCENARIO=self.scenario)
        result = subprocess.run([sys.executable, str(TEAM), command, "--run", str(self.run), *map(str, args)],
                                capture_output=True, text=True, env=env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def load(self, name="state.json"):
        return json.loads((self.run / name).read_text())

    def start(self):
        self.command("init", "--brief", self.brief, "--workspace", self.workspace, "--claude-bin", FAKE)
        self.command("prepare")
        self.command("approve")

    def inputs(self):
        return [json.loads(p.read_text()) for p in sorted((self.run / "calls").glob("*.input.json"))]

    def c_results(self):
        return [json.loads(line) for p in sorted((self.run / "calls").glob("*-C-*.stdout.jsonl"))
                for line in p.read_text().splitlines() if json.loads(line).get("type") == "result"]

    def test_handoff_is_initialized_without_starting_an_agent(self):
        self.command("init", "--brief", self.brief, "--workspace", self.workspace, "--claude-bin", FAKE)
        self.assertEqual(self.load()["status"], "new")
        self.assertFalse((self.run / "calls").exists())
        self.assertEqual(self.load()["models"], {"A": "opus", "B": "opus", "C": "sonnet"})

    def test_initial_approval_is_required(self):
        self.command("init", "--brief", self.brief, "--workspace", self.workspace, "--claude-bin", FAKE)
        self.command("prepare")
        self.command("run", ok=False)
        self.assertEqual(self.load()["status"], "awaiting_approval")

    def test_negative_evidence_converges_on_first_round_without_rework(self):
        self.start()
        self.command("run")
        state = self.load()
        self.assertEqual(state["status"], "report_ready")
        self.assertEqual(len(state["rounds"]), 1)
        self.assertEqual(state["rework_count"], 0)
        self.assertTrue((self.run / "decision-report.md").exists())
        self.assertNotIn("approved_at", state)

    def test_c_checklist_is_independent_and_session_is_resumed(self):
        self.start()
        self.command("run")
        calls = self.inputs()
        self.assertEqual([x["phase"] for x in calls], ["analysis", "checklist", "experiment", "review", "final"])
        self.assertEqual(set(calls[1]["input"]), {"brief"})
        self.assertNotIn("private recommendation", json.dumps(calls[1]))
        sessions = self.load()["sessions"]
        self.assertEqual(set(sessions), {"A", "B", "C"})
        self.assertEqual(len(set(sessions.values())), 3)
        c_results = self.c_results()
        self.assertEqual(c_results[0]["session_id"], c_results[-1]["session_id"])

    def test_three_failed_rounds_escalate_and_never_launch_a_fourth(self):
        self.scenario = "never"
        self.start()
        self.command("run")
        self.assertEqual(self.load()["status"], "escalated")
        self.assertEqual(len(self.load()["rounds"]), 3)
        self.assertEqual(self.load()["rework_count"], 2)
        self.assertEqual(self.inputs()[-1]["phase"], "escalation")
        before = len(self.inputs())
        self.command("run", ok=False)
        self.assertEqual(len(self.inputs()), before)

    def test_review_feedback_routes_to_a_then_b(self):
        self.scenario = "a_fix"
        self.start()
        self.command("run")
        calls = self.inputs()
        self.assertEqual([x["phase"] for x in calls], ["analysis", "checklist", "experiment", "review", "correction", "experiment", "review", "final"])
        second_b = calls[5]["input"]
        self.assertTrue(second_b["feedback"]["corrections"]["A"])
        self.assertIn("Corrected architecture", second_b["analysis_correction"]["report"])

    def test_model_mismatch_stops_before_b(self):
        self.scenario = "same_model"
        self.start()
        self.command("run", ok=False)
        self.assertEqual(len(self.load()["rounds"]), 0)
        self.assertIn("model", self.command("status").stdout.lower())

    def test_shared_auxiliary_model_does_not_break_role_independence(self):
        self.scenario = "shared_helper"
        self.start()
        self.command("run")
        self.assertEqual(self.load()["status"], "report_ready")
        self.assertEqual(self.load()["actual_models"]["C"], ["claude-sonnet-test"])

    def test_missing_primary_model_metadata_stops_work(self):
        self.scenario = "missing_primary"
        self.command("init", "--brief", self.brief, "--workspace", self.workspace, "--claude-bin", FAKE)
        self.command("prepare", ok=False)
        self.assertEqual(self.load()["status"], "new")

    def test_later_primary_model_fallback_overlap_stops_before_b(self):
        self.scenario = "fallback_overlap"
        self.start()
        self.command("run", ok=False)
        self.assertEqual(len(self.load()["rounds"]), 0)

    def test_final_approval_rejects_brief_drift_without_mutating_metrics_or_timer(self):
        self.start()
        self.command("run")
        self.command("human-start")
        path = self.run / "approved-brief.json"
        original = path.read_text()
        before = self.load("metrics.json")
        for field in ("question", "scope", "acceptance_criteria"):
            with self.subTest(field=field):
                brief = json.loads(original)
                if field == "acceptance_criteria":
                    brief[field].append({"id": "AC2", "description": "new threshold"})
                else:
                    brief[field] = "changed " + field
                path.write_text(json.dumps(brief))
                self.command("finish", "--human-seconds", "99", ok=False)
                self.assertEqual(self.load()["status"], "report_ready")
                self.assertNotIn("approved_at", self.load())
                self.assertIn("human_started_at", self.load())
                self.assertEqual(self.load("metrics.json"), before)
        self.command("resolve", "--note", "Approve the additional criterion")
        self.command("run")
        self.command("finish", "--human-seconds", "99")

    def test_inconclusive_approval_also_rejects_brief_drift(self):
        self.scenario = "never"
        self.start()
        self.command("run")
        path = self.run / "approved-brief.json"
        brief = json.loads(path.read_text())
        brief["scope"] = "changed"
        path.write_text(json.dumps(brief))
        self.command("finish", "--human-seconds", "10", "--inconclusive", ok=False)
        self.assertEqual(self.load()["status"], "escalated")
        self.assertNotIn("approved_at", self.load())

    def assert_pause_checkpoint(self, role, scenario):
        self.start()
        original_save = team.Team.save
        def interrupted_save(instance):
            original_save(instance)
            rounds = instance.state["rounds"]
            if rounds and rounds[-1].get(role, {}).get("needs_human"):
                raise KeyboardInterrupt()
        with mock.patch.dict(os.environ, FAKE_SCENARIO=scenario):
            with mock.patch.object(team.Team, "save", interrupted_save):
                with self.assertRaises(KeyboardInterrupt):
                    team.Team(self.run).run()
        self.assertEqual(self.load()["status"], "needs_human")
        self.assertTrue(self.load()["human_request"])
        before = len(self.inputs())
        self.command("run", ok=False)
        self.assertEqual(len(self.inputs()), before)

    def test_b_human_gate_survives_checkpoint_interruption(self):
        self.assert_pause_checkpoint("B", "pause_b")

    def test_c_human_gate_survives_checkpoint_interruption(self):
        self.assert_pause_checkpoint("C", "pause")

    def test_c_report_write_failure_preserves_pending_human_gate(self):
        self.start()
        original_write = Path.write_text
        def broken_report(path, *args, **kwargs):
            if path.name == "round-1-review.md":
                raise OSError("disk unavailable")
            return original_write(path, *args, **kwargs)
        with mock.patch.dict(os.environ, FAKE_SCENARIO="pause"):
            with mock.patch.object(Path, "write_text", broken_report):
                with self.assertRaises(OSError):
                    team.Team(self.run).run()
        self.assertEqual(self.load()["status"], "needs_human")
        self.command("run", ok=False)

    def test_edited_approved_brief_requires_explicit_resolution(self):
        self.start()
        path = self.run / "approved-brief.json"
        brief = json.loads(path.read_text())
        brief["scope"] = "changed scope"
        path.write_text(json.dumps(brief))
        self.command("run", ok=False)
        self.assertEqual(len(self.load()["rounds"]), 0)
        self.command("resolve", "--note", "Human approves the changed scope")
        self.command("run")
        self.assertEqual(self.load()["status"], "report_ready")

    def test_human_request_pauses_the_loop(self):
        self.scenario = "pause"
        self.start()
        self.command("run")
        self.assertEqual(self.load()["status"], "needs_human")
        self.assertEqual(len(self.load()["rounds"]), 1)
        self.command("run", ok=False)
        self.command("resolve", "--note", "Proceed within existing scope")
        self.command("run")
        self.assertEqual(self.load()["status"], "report_ready")

    def test_invalid_cli_output_resumes_c_without_repeating_b(self):
        self.scenario = "bad_json"
        self.start()
        self.command("run", ok=False)
        self.assertEqual(len(self.load()["rounds"]), 1)
        self.scenario = "pass"
        self.command("run")
        self.assertEqual(sum(x["phase"] == "experiment" for x in self.inputs()), 1)

    def test_final_report_error_resumes_a_without_repeating_b(self):
        self.scenario = "report_error"
        self.start()
        self.command("run", ok=False)
        self.scenario = "pass"
        self.command("run")
        self.assertEqual(len(self.load()["rounds"]), 1)
        self.assertEqual(self.load()["status"], "report_ready")

    def test_missing_criteria_and_string_booleans_do_not_pass(self):
        self.start()
        for scenario in ("missing_check", "bad_bool"):
            self.scenario = scenario
            self.command("run", ok=False)
            self.assertNotEqual(self.load()["status"], "report_ready")
        self.scenario = "pass"
        self.command("run")
        self.assertEqual(len(self.load()["rounds"]), 1)

    def test_four_metrics_require_human_approval_and_defects_deduplicate(self):
        self.start()
        self.command("run")
        self.command("human-add", "--seconds", "20")
        self.command("human-add", "--seconds", "22")
        self.command("defect", "--id", "wrong-source", "--note", "First discovered at final review")
        self.command("defect", "--id", "wrong-source", "--note", "Duplicate")
        self.command("finish", "--major-rework", "1")
        metrics = self.load("metrics.json")
        self.assertEqual(set(metrics), {"Lead Time", "Human Review Time", "Major Rework", "Defects"})
        self.assertGreaterEqual(metrics["Lead Time"], 0)
        self.assertEqual(metrics["Human Review Time"], 42)
        self.assertEqual(metrics["Major Rework"], 1)
        self.assertEqual(metrics["Defects"], 1)
        self.command("finalize", ok=False)
        state = self.load()
        state["approved_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)).isoformat()
        (self.run / "state.json").write_text(json.dumps(state))
        self.command("defect", "--id", "too-late", "--note", "outside observation window", ok=False)
        self.command("finalize")
        self.assertEqual(self.load()["status"], "finalized")
        self.command("human-add", "--seconds", "1", ok=False)

    def test_finish_requires_recorded_human_effort(self):
        self.start()
        self.command("run")
        self.command("finish", ok=False)
        self.command("finish", "--human-seconds", "30")
        self.assertEqual(self.load("metrics.json")["Human Review Time"], 30)

    def test_escalation_requires_explicit_inconclusive_approval(self):
        self.scenario = "never"
        self.start()
        self.command("run")
        self.command("finish", "--human-seconds", "30", ok=False)
        self.command("finish", "--human-seconds", "30", "--inconclusive")
        self.assertEqual(self.load()["outcome"], "inconclusive")

    def test_failed_b_attempt_keeps_prior_c_feedback_on_retry(self):
        self.scenario = "experiment_error"
        self.start()
        self.command("run", ok=False)
        self.assertEqual(len(self.load()["rounds"]), 2)
        self.scenario = "pass"
        self.command("run")
        experiments = [x for x in self.inputs() if x["phase"] == "experiment"]
        self.assertEqual(experiments[-1]["input"]["round"], 3)
        self.assertIsNotNone(experiments[-1]["input"]["feedback"])
        self.assertEqual(experiments[-1]["input"]["feedback"]["corrections"]["B"], ["repeat measurement"])

    def test_human_final_review_can_return_work_without_resetting_rounds(self):
        self.start()
        self.command("run")
        self.scenario = "human_rework"
        self.command("resolve", "--note", "Final review found a missing observation")
        self.command("run")
        self.assertEqual(self.load()["status"], "report_ready")
        self.assertEqual(len(self.load()["rounds"]), 2)
        self.assertEqual(self.load()["rework_count"], 1)

    def test_failed_b_attempts_also_obey_three_attempt_limit(self):
        self.scenario = "experiment_all_fail"
        self.start()
        for _ in range(3):
            self.command("run", ok=False)
        self.command("run")
        self.assertEqual(self.load()["status"], "escalated")
        self.assertEqual(sum(x["phase"] == "experiment" for x in self.inputs()), 3)

    def test_final_review_after_third_round_cannot_launch_fourth(self):
        self.scenario = "third_pass"
        self.start()
        self.command("run")
        self.scenario = "never"
        self.command("resolve", "--note", "Final review rejects the evidence")
        self.command("run")
        self.assertEqual(self.load()["status"], "escalated")
        self.assertEqual(sum(x["phase"] == "experiment" for x in self.inputs()), 3)

    def test_changed_brief_starts_fresh_c_context_without_resetting_round_count(self):
        self.scenario = "pause"
        self.start()
        self.command("run")
        old_c_session = self.load()["sessions"]["C"]
        path = self.run / "approved-brief.json"
        brief = json.loads(path.read_text())
        brief["acceptance_criteria"].append({"id": "AC2", "description": "Measure throughput"})
        path.write_text(json.dumps(brief))
        self.command("resolve", "--note", "Approve additional evidence criterion")
        self.command("run")
        checklists = [x for x in self.inputs() if x["phase"] == "checklist"]
        self.assertEqual(len(checklists), 2)
        self.assertIsNone(checklists[-1]["resume_session"])
        self.assertEqual(set(checklists[-1]["input"]), {"brief"})
        self.assertNotEqual(self.load()["sessions"]["C"], old_c_session)
        self.assertEqual(len(self.load()["rounds"]), 2)

    def test_manual_timer_and_invalid_time_preserve_recorded_effort(self):
        self.start()
        self.command("human-start")
        self.command("human-start", ok=False)
        self.command("human-stop")
        total = self.load()["human_seconds"]
        self.assertGreater(total, 0)
        self.command("human-add", "--seconds", "-1", ok=False)
        self.assertEqual(self.load()["human_seconds"], total)

    def test_single_writer_lock_prevents_duplicate_execution(self):
        self.start()
        with (self.run / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.command("run", ok=False)
            self.assertIn("Another command", result.stderr)
            self.command("status")
        self.assertEqual(len(self.load()["rounds"]), 0)


if __name__ == "__main__":
    unittest.main()
