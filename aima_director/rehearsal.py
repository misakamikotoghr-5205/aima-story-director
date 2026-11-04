"""Bounded symbolic rehearsal for the DSL's fixed event snapshots.

The implementation is independent. Design references and license boundaries are
documented in docs/landscape.md; no third-party robot runtime is included.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .core import ValidationError, _hash, simulate, validate, verify_audit, write_artifacts


def _constrain(current: dict, event: str, value: Any, matches: bool) -> dict | None:
    """An event has one immutable value, or is missing, throughout a rehearsal."""
    constraints = deepcopy(current)
    rule = constraints.setdefault(event, {"excluded": []})
    if matches:
        if ("equal" in rule and rule["equal"] != value) or value in rule["excluded"]:
            return None
        rule["equal"] = value
    else:
        if "equal" in rule and rule["equal"] == value:
            return None
        if value not in rule["excluded"]:
            rule["excluded"].append(value)
    return constraints


def _unequal_value(kind: str, excluded: list) -> tuple[bool, Any]:
    if kind == "boolean":
        candidates = [False, True]
    elif kind == "number":
        # n forbidden equality values cannot exclude all n+1 finite integers.
        candidates = list(range(len(excluded) + 1))
    else:
        candidates = [""] + [f"other-{index}" for index in range(len(excluded) + 1)]
    for value in candidates:
        if value not in excluded:
            return True, value
    return False, None


def rehearse(spec: dict, *, max_routes: int = 64, max_cases: int = 128,
             max_expansions: int = 4096, max_commands: int = 50000) -> dict:
    """Rehearse feasible decisions and representative missing/present inputs.

    Completeness is relative to this acyclic equality-only DSL with one fixed
    event snapshot, not all sensor streams or every number/string input.
    Limits are explicit; hitting one never labels untested branches infeasible.
    """
    validate(spec)
    for name, value, maximum in (("max_routes", max_routes, 256), ("max_cases", max_cases, 256),
                                 ("max_expansions", max_expansions, 20000), ("max_commands", max_commands, 100000)):
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValidationError(f"{name}: expected an integer in 1..{maximum}")
    paths = []
    stack = [(spec["entry"], [], {}, [])]
    reasons = []
    expansions = 0
    contradictions = 0
    while stack:
        if len(paths) >= max_routes or expansions >= max_expansions:
            reasons.append("route-limit" if len(paths) >= max_routes else "expansion-limit")
            break
        scene_id, route, constraints, choices = stack.pop()
        expansions += 1
        route = route + [scene_id]
        steps = spec["scenes"][scene_id]["steps"]
        branch = steps[-1] if steps[-1]["type"] == "branch" else None
        if branch is None:
            paths.append({"route": route, "constraints": constraints, "choices": choices})
            continue
        # Push else first so deterministic DFS visits the authored then path first.
        for outcome, matched in (("else", False), ("then", True)):
            refined = _constrain(constraints, branch["event"], branch["equals"], matched)
            if refined is None:
                contradictions += 1
                continue
            choice = {"command_id": f"{scene_id}:{branch['id']}", "outcome": outcome,
                      "event": branch["event"], "target": branch[outcome]}
            stack.append((branch[outcome], route, refined, choices + [choice]))

    candidates = []
    seen_fixtures = set()
    case_limited = False

    def add_candidate(path, fixture, label):
        nonlocal case_limited
        key = json.dumps(fixture, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if key in seen_fixtures:
            return
        seen_fixtures.add(key)
        if len(candidates) >= max_cases:
            case_limited = True
            return
        candidates.append((path, fixture, label))

    # First cover decision paths; negative-input variants must not crowd them out.
    for path in paths:
        fixture = {event: deepcopy(rule["equal"]) for event, rule in path["constraints"].items() if "equal" in rule}
        add_candidate(path, fixture, "minimal snapshot; unconstrained comparisons use missing events")
    for path in paths:
        baseline = {event: deepcopy(rule["equal"]) for event, rule in path["constraints"].items() if "equal" in rule}
        for event, rule in path["constraints"].items():
            if "equal" not in rule:
                found, other = _unequal_value(spec["events"][event], rule["excluded"])
                if found:
                    add_candidate(path, baseline | {event: other}, f"present nonmatching value for {event}")
    if case_limited:
        reasons.append("case-limit")

    cases = []
    commands = 0
    for path, fixture, label in candidates:
        command_count = sum(len(spec["scenes"][scene]["steps"]) for scene in path["route"])
        if commands + command_count > max_commands:
            if "command-limit" not in reasons:
                reasons.append("command-limit")
            continue
        audit = simulate(spec, fixture)  # There is deliberately no hardware mode.
        actual_choices = [{"command_id": item["command_id"],
                           "outcome": "then" if item["decision"]["matched"] else "else",
                           "event": item["decision"]["event"], "target": item["decision"]["selected_scene"]}
                          for item in audit["timeline"] if item["type"] == "branch"]
        if audit["route"] != path["route"] or actual_choices != path["choices"]:
            raise ValidationError("Internal rehearsal error: generated fixture did not reproduce its symbolic decisions")
        commands += command_count
        cases.append({"id": f"case-{len(cases) + 1:03d}", "label": label, "events": fixture,
                      "route": audit["route"], "duration_ms": audit["duration_ms"],
                      "decisions": actual_choices, "audit": audit})

    complete = not reasons
    coverage = []
    reached_scenes = {scene for case in cases for scene in case["route"]}
    for scene_id, scene in spec["scenes"].items():
        branch = scene["steps"][-1]
        if branch["type"] != "branch":
            continue
        for outcome in ("then", "else"):
            command_id = f"{scene_id}:{branch['id']}"
            matching = [case for case in cases if any(choice["command_id"] == command_id and choice["outcome"] == outcome for choice in case["decisions"])]
            coverage.append({"command_id": command_id, "event": branch["event"], "equals": branch["equals"],
                             "outcome": outcome, "target": branch[outcome],
                             "status": "covered" if matching else "infeasible" if complete else "unexplored",
                             "case_ids": [case["id"] for case in matching],
                             "missing_event_case_ids": [case["id"] for case in matching if branch["event"] not in case["events"]]})
    result = {
        "format_version": 1, "show_id": spec["id"], "title": spec["title"],
        "source_sha256": _hash(spec), "mode": "dry-run", "hardware_sent": False,
        "complete": complete, "limit_reasons": reasons,
        "limits": {"max_routes": max_routes, "max_cases": max_cases, "max_expansions": max_expansions, "max_commands": max_commands},
        "stats": {"feasible_paths_found": len(paths), "cases": len(cases), "commands": commands,
                  "covered_outcomes": sum(row["status"] == "covered" for row in coverage),
                  "total_outcomes": len(coverage), "contradictory_prefixes_pruned": contradictions,
                  "scene_expansions": expansions},
        "coverage": coverage, "unreached_scenes": sorted(set(spec["scenes"]) - reached_scenes),
        "cases": cases,
        "scope_note": "Complete means all feasible decision paths plus representative missing/present nonmatching fixtures within this fixed-snapshot equality DSL. It does not prove live sensor, motion, timing, or hardware safety.",
    }
    result["manifest_hash"] = _hash(result)
    return result


def verify_rehearsal(suite: Any) -> bool:
    try:
        if (not isinstance(suite, dict) or suite.get("format_version") != 1
                or suite.get("mode") != "dry-run" or suite.get("hardware_sent") is not False):
            return False
        if _hash({key: value for key, value in suite.items() if key != "manifest_hash"}) != suite["manifest_hash"]:
            return False
        return all(case["id"] == f"case-{index + 1:03d}" and verify_audit(case["audit"]) and case["audit"]["events"] == case["events"]
                   and case["audit"]["route"] == case["route"]
                   and case["audit"]["source_sha256"] == suite["source_sha256"] for index, case in enumerate(suite["cases"]))
    except (KeyError, TypeError, ValueError, RecursionError):
        return False


def write_rehearsal_artifacts(suite: dict, output: str | Path) -> list[Path]:
    if not verify_rehearsal(suite):
        raise ValidationError("Cannot export: rehearsal integrity verification failed")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for case in suite["cases"]:
        directory = output / case["id"]
        paths.extend(write_artifacts(case["audit"], directory))
        fixture_path = directory / "events.json"
        fixture_path.write_text(json.dumps(case["events"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths.append(fixture_path)
    report = output / "rehearsal.json"
    report.write_text(json.dumps(suite, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [f"# {suite['title']} — branch rehearsal", "", "**DRY-RUN ONLY. Hardware commands sent: 0.**", "",
             f"Status: {'complete within declared scope' if suite['complete'] else 'INCOMPLETE; limits reached'}.",
             f"Cases: {suite['stats']['cases']}. Feasible decision paths found: {suite['stats']['feasible_paths_found']}.",
             f"Limits reached: {', '.join(suite['limit_reasons']) or 'none'}.", "", suite["scope_note"], "",
             "| Branch | Outcome | Target | Status | Replaying fixtures |", "| --- | --- | --- | --- | --- |"]
    for row in suite["coverage"]:
        links = ", ".join(f"[{case}](./{case}/events.json)" for case in row["case_ids"]) or "—"
        lines.append(f"| {row['command_id']} | {row['outcome']} | {row['target']} | {row['status']} | {links} |")
    lines.extend(["", "Unreached scenes: " + (", ".join(suite["unreached_scenes"]) or "none") + ".",
                  "An unreached outcome is labeled infeasible only after complete constraint exploration. Otherwise it remains unexplored.",
                  "", "Checksums detect edits; they are not signatures or proof of robot execution.", ""])
    summary = output / "rehearsal.md"
    summary.write_text("\n".join(lines), encoding="utf-8")
    return paths + [report, summary]
