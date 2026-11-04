from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aima_director import (ValidationError, load_json, rehearse, simulate, verify_audit,
                           verify_rehearsal, write_rehearsal_artifacts)

ROOT = Path(__file__).resolve().parents[1]


def terminal(label):
    return {"label": label, "steps": [{"id": "pause", "type": "wait", "at_ms": 0, "duration_ms": 1}]}


def branch(event, equals, yes, no):
    return {"label": "Decision", "steps": [{"id": "choose", "type": "branch", "at_ms": 0,
             "event": event, "equals": equals, "then": yes, "else": no}]}


def correlated_spec(second_equals=False):
    return {"schema_version": 1, "id": "correlated", "title": "Correlated conditions", "entry": "start",
            "events": {"visitor": "boolean"}, "scenes": {
                "start": branch("visitor", True, "repeat", "absent"),
                "repeat": branch("visitor", second_equals, "unreachable", "greet"),
                "absent": terminal("No visitor"), "unreachable": terminal("Inconsistent condition"),
                "greet": terminal("Greeting"),
            }}


class RehearsalTests(unittest.TestCase):
    def test_all_examples_generate_replayable_feasible_routes_without_hardware(self):
        for name in ("welcome", "exhibition", "distance-reminder"):
            spec = load_json(ROOT / "examples" / f"{name}.json")
            untouched = deepcopy(spec)
            suite = rehearse(spec)
            self.assertEqual(spec, untouched)
            self.assertTrue(suite["complete"])
            self.assertTrue(verify_rehearsal(suite))
            self.assertFalse(suite["hardware_sent"])
            self.assertEqual(suite["stats"]["covered_outcomes"], suite["stats"]["total_outcomes"])
            for case in suite["cases"]:
                self.assertEqual(simulate(spec, case["events"]), case["audit"])
                self.assertTrue(verify_audit(case["audit"]))
                self.assertTrue(all(not entry["adapter_result"]["hardware_sent"] for entry in case["audit"]["timeline"]))

    def test_correlated_conditions_expose_a_structurally_reachable_but_infeasible_branch(self):
        suite = rehearse(correlated_spec())
        self.assertTrue(suite["complete"])
        self.assertEqual(suite["stats"]["feasible_paths_found"], 2)
        self.assertIn("unreachable", suite["unreached_scenes"])
        row = next(row for row in suite["coverage"] if row["command_id"] == "repeat:choose" and row["outcome"] == "then")
        self.assertEqual(row["status"], "infeasible")
        self.assertEqual(row["case_ids"], [])
        self.assertGreater(suite["stats"]["contradictory_prefixes_pruned"], 0)

    def test_missing_event_is_distinct_from_explicit_false_and_can_be_the_only_feasible_else(self):
        spec = {"schema_version": 1, "id": "missing", "title": "Missing is not false", "entry": "start",
                "events": {"visitor": "boolean"}, "scenes": {
                    "start": branch("visitor", True, "yes", "repeat"),
                    "repeat": branch("visitor", False, "no", "unknown"),
                    "yes": terminal("Yes"), "no": terminal("No"), "unknown": terminal("Unknown"),
                }}
        suite = rehearse(spec)
        self.assertTrue(suite["complete"])
        self.assertEqual(suite["stats"]["feasible_paths_found"], 3)
        fixtures = [case["events"] for case in suite["cases"]]
        self.assertIn({}, fixtures)
        self.assertIn({"visitor": False}, fixtures)
        self.assertIn({"visitor": True}, fixtures)
        unknown = next(case for case in suite["cases"] if case["route"][-1] == "unknown")
        self.assertNotIn("visitor", unknown["events"])
        self.assertTrue(any(row["missing_event_case_ids"] for row in suite["coverage"]))

    def test_number_and_string_constraints_receive_valid_present_nonmatching_examples(self):
        spec = {"schema_version": 1, "id": "typed", "title": "Typed conditions", "entry": "start",
                "events": {"count": "number", "language": "string"}, "scenes": {
                    "start": branch("count", 1, "choose-language", "none"),
                    "choose-language": branch("language", "zh", "chinese", "other"),
                    "none": terminal("None"), "chinese": terminal("Chinese"), "other": terminal("Other"),
                }}
        suite = rehearse(spec)
        self.assertTrue(suite["complete"])
        self.assertTrue(any("count" in case["events"] and case["events"]["count"] != 1 for case in suite["cases"]))
        self.assertTrue(any("language" in case["events"] and case["events"]["language"] != "zh" for case in suite["cases"]))
        for case in suite["cases"]:
            if "count" in case["events"]:
                self.assertIsNot(type(case["events"]["count"]), bool)

    def test_parallel_branch_targets_still_cover_both_decisions(self):
        spec = {"schema_version": 1, "id": "same-target", "title": "Same target", "entry": "start",
                "events": {"flag": "boolean"}, "scenes": {"start": branch("flag", True, "end", "end"), "end": terminal("End")}}
        suite = rehearse(spec)
        self.assertEqual(suite["stats"]["feasible_paths_found"], 2)
        self.assertEqual(suite["stats"]["covered_outcomes"], 2)

    def test_limits_never_label_untested_outcomes_infeasible(self):
        for limits in ({"max_routes": 1}, {"max_cases": 1}, {"max_expansions": 1}, {"max_commands": 1}):
            suite = rehearse(correlated_spec(), **limits)
            self.assertFalse(suite["complete"], limits)
            self.assertTrue(suite["limit_reasons"])
            self.assertFalse(any(row["status"] == "infeasible" for row in suite["coverage"]))
            self.assertTrue(any(row["status"] == "unexplored" for row in suite["coverage"]))
        for invalid in ({"max_cases": True}, {"max_routes": 0}, {"max_commands": 100001}):
            with self.assertRaises(ValidationError):
                rehearse(correlated_spec(), **invalid)

    def test_exported_fixtures_and_timelines_reproduce_audits_and_tampering_is_rejected(self):
        spec = correlated_spec()
        suite = rehearse(spec)
        self.assertEqual(suite, rehearse(spec))
        with tempfile.TemporaryDirectory() as temp:
            paths = write_rehearsal_artifacts(suite, temp)
            self.assertIn(Path(temp) / "rehearsal.md", paths)
            saved = load_json(Path(temp) / "rehearsal.json")
            self.assertTrue(verify_rehearsal(saved))
            for case in suite["cases"]:
                events = load_json(Path(temp) / case["id"] / "events.json")
                audit = load_json(Path(temp) / case["id"] / "timeline.json")
                self.assertEqual(audit, simulate(spec, events))
            changed = deepcopy(suite)
            changed["coverage"][0]["status"] = "infeasible"
            self.assertFalse(verify_rehearsal(changed))
            with self.assertRaises(ValidationError):
                write_rehearsal_artifacts(changed, Path(temp) / "bad")

    def test_cli_reports_incomplete_rehearsal_with_nonzero_status(self):
        with tempfile.TemporaryDirectory() as temp:
            command = [sys.executable, "-m", "aima_director", "rehearse", "examples/welcome.json", "--out", temp, "--max-cases", "1"]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn("INCOMPLETE", result.stdout)
            self.assertIn("hardware commands sent: 0", result.stdout)
            self.assertTrue((Path(temp) / "rehearsal.json").exists())


if __name__ == "__main__":
    unittest.main()
