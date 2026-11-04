import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from aima_director import ValidationError, load_json, simulate, validate, verify_audit, write_artifacts
from aima_director.core import render_svg

ROOT = Path(__file__).resolve().parents[1]


def example(name="welcome"):
    return load_json(ROOT / "examples" / f"{name}.json")


def single_scene(steps):
    return {"schema_version": 1, "id": "test-show", "title": "Test show", "entry": "main", "scenes": {"main": {"label": "Main", "steps": steps}}}


def speech(step_id="hello", at=0, duration=1000):
    return {"id": step_id, "type": "speech", "at_ms": at, "duration_ms": duration, "text": "Hello"}


class DirectorTests(unittest.TestCase):
    def test_all_examples_and_all_boolean_event_combinations_finish_with_valid_audits(self):
        for name in ("welcome", "exhibition", "distance-reminder"):
            spec = example(name)
            event_names = list(spec["events"])
            for values in itertools.product([False, True], repeat=len(event_names)):
                with self.subTest(name=name, values=values):
                    result = simulate(spec, dict(zip(event_names, values)))
                    self.assertTrue(verify_audit(result))
                    self.assertFalse(result["hardware_sent"])
                    self.assertTrue(all(not item["adapter_result"]["hardware_sent"] for item in result["timeline"]))
                    self.assertLessEqual(len(result["route"]), len(spec["scenes"]))

    def test_missing_event_and_explicit_false_are_audited_differently(self):
        missing = simulate(example(), {})
        explicit = simulate(example(), {"visitor_present": False})
        self.assertEqual(missing["route"], ["arrival", "standby"])
        self.assertEqual(missing["route"], explicit["route"])
        self.assertFalse(missing["timeline"][1]["decision"]["present"])
        self.assertTrue(explicit["timeline"][1]["decision"]["present"])
        self.assertNotEqual(missing["manifest_hash"], explicit["manifest_hash"])

    def test_event_type_is_strict_and_typos_are_not_silently_ignored(self):
        for events in ({"visitor_present": 1}, {"visitor_present": "true"}, {"visitor_presnt": True}, []):
            with self.subTest(events=events), self.assertRaises(ValidationError):
                simulate(example(), events)

    def test_cross_channel_concurrency_is_allowed_but_same_channel_overlap_is_rejected(self):
        gesture = {"id": "wave", "type": "gesture", "at_ms": 100, "duration_ms": 500, "name": "wave", "amplitude": 0.2, "speed": 0.3}
        self.assertEqual(simulate(single_scene([speech(), gesture]))["duration_ms"], 1000)
        with self.assertRaisesRegex(ValidationError, "overlapping speech"):
            validate(single_scene([speech(), speech("second", at=999)]))
        validate(single_scene([speech(), speech("second", at=1000)]))

    def test_timing_and_normalized_parameters_reject_boolean_negative_and_nonfinite_values(self):
        for value in (True, -1, 0.5, float("nan"), float("inf"), 600001):
            step = speech()
            step["at_ms"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate(single_scene([step]))
        gesture = {"id": "wave", "type": "gesture", "at_ms": 0, "duration_ms": 1000, "name": "wave", "amplitude": 0.3, "speed": 0.3}
        for parameter, value in (("speed", 0), ("speed", True), ("amplitude", 1.1), ("amplitude", float("nan")), ("amplitude", 10 ** 500)):
            step = dict(gesture, **{parameter: value})
            with self.subTest(parameter=parameter, value=value), self.assertRaises(ValidationError):
                validate(single_scene([step]))

    def test_branch_cannot_cut_off_an_unfinished_action(self):
        spec = example()
        spec["scenes"]["greeting"]["steps"][-1]["at_ms"] = 8000
        with self.assertRaisesRegex(ValidationError, "all scene actions finish"):
            validate(spec)

    def test_cycles_missing_targets_and_unreachable_scenes_are_rejected(self):
        cycle = example()
        cycle["scenes"]["arrival"]["steps"][-1]["then"] = "arrival"
        missing = example()
        missing["scenes"]["arrival"]["steps"][-1]["else"] = "missing"
        unreachable = example()
        unreachable["scenes"]["unused"] = {"label": "Unused", "steps": [speech()]}
        for spec, message in ((cycle, "cycle"), (missing, "defined scene"), (unreachable, "unreachable")):
            with self.subTest(message=message), self.assertRaisesRegex(ValidationError, message):
                validate(spec)

    def test_unknown_fields_and_wrong_container_types_have_readable_validation_errors(self):
        mutations = [
            lambda s: s.update(endpoint="http://robot.invalid"),
            lambda s: s["events"].update(visitor_present=[]),
            lambda s: s["scenes"]["arrival"]["steps"][0].update(type=[]),
            lambda s: s["scenes"]["greeting"]["steps"][1].update(name=[]),
            lambda s: s["scenes"]["arrival"]["steps"][0].update(duration_mss=1000),
        ]
        for mutate in mutations:
            spec = example()
            mutate(spec)
            with self.subTest(mutate=mutate), self.assertRaises(ValidationError):
                validate(spec)

    def test_repeated_simulation_is_deterministic_and_does_not_change_inputs(self):
        spec = example()
        events = {"visitor_present": True, "needs_directions": True}
        before = copy.deepcopy((spec, events))
        first, second = simulate(spec, events), simulate(spec, events)
        self.assertEqual(first, second)
        self.assertEqual((spec, events), before)
        first["events"]["visitor_present"] = False
        self.assertEqual((spec, events), before)

    def test_integrity_verification_detects_changed_commands_events_and_removed_entries(self):
        original = simulate(example(), {"visitor_present": True})
        mutations = [
            lambda a: a["timeline"][0].update(end_ms=123),
            lambda a: a["events"].update(visitor_present=False),
            lambda a: a["timeline"].pop(),
            lambda a: a.update(hardware_sent=True),
        ]
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(changed)
            with self.subTest(mutate=mutate):
                self.assertFalse(verify_audit(changed))
        for bad in (None, {}, {"format_version": 1}, [], True):
            self.assertFalse(verify_audit(bad))

    def test_hardware_mode_fails_before_export(self):
        with self.assertRaisesRegex(ValidationError, "not implemented"):
            simulate(example(), mode="hardware")
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, "-m", "aima_director", "simulate", "examples/welcome.json", "--mode", "hardware", "--out", str(Path(tmp) / "artifacts")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("not implemented", result.stderr)
            self.assertFalse((Path(tmp) / "artifacts").exists())

    def test_exported_svg_is_valid_xml_and_escapes_user_text(self):
        spec = single_scene([dict(speech(), text='<script>alert("x")</script> & hello')])
        spec["title"] = '<robot & "guest">'
        audit = simulate(spec)
        rendered = render_svg(audit)
        root = ET.fromstring(rendered)
        self.assertEqual(root.attrib["role"], "img")
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&lt;robot &amp;", rendered)

    def test_cli_roundtrip_and_export_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "preview"
            result = subprocess.run([sys.executable, "-m", "aima_director", "simulate", "examples/welcome.json", "--events", "examples/welcome.events.json", "--out", str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("hardware commands sent: 0", result.stdout)
            self.assertEqual({path.name for path in output.iterdir()}, {"timeline.json", "timeline.svg", "execution-checklist.md", "transcript.txt"})
            self.assertTrue(verify_audit(load_json(output / "timeline.json")))
            check = subprocess.run([sys.executable, "-m", "aima_director", "verify", str(output / "timeline.json")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertIn("您好", (output / "transcript.txt").read_text(encoding="utf-8"))

    def test_duplicate_json_fields_and_nan_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            for text in ('{"id":"one","id":"two"}', '{"speed":NaN}', '{"speed":Infinity}', '{bad json}'):
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(ValidationError):
                    load_json(path)

    def test_invalid_audit_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValidationError):
                write_artifacts({}, Path(tmp) / "new")
            self.assertFalse((Path(tmp) / "new").exists())


if __name__ == "__main__":
    unittest.main()
