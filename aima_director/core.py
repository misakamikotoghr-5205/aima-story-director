"""Validate a small show DSL, simulate its timing, and export review artifacts."""

from __future__ import annotations

import hashlib
import html
import json
import math
from pathlib import Path
import re
from typing import Any

MAX_FILE_BYTES = 2_000_000
MAX_SCENE_MS = 600_000
MAX_SHOW_MS = 1_800_000
MAX_SCENES = 128
MAX_STEPS = 256
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
GESTURES = {"wave", "nod", "point-left", "point-right", "open-arms", "stop-hand", "neutral"}
EVENT_TYPES = {"boolean": bool, "number": (int, float), "string": str}


class ValidationError(ValueError):
    """An actionable collection of input errors."""

    def __init__(self, errors: str | list[str]):
        self.errors = [errors] if isinstance(errors, str) else errors
        super().__init__("\n".join(self.errors))


def _reject_constant(value: str) -> None:
    raise ValidationError(f"JSON contains a non-finite number: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"JSON contains a duplicate key: {key!r}")
        result[key] = value
    return result


def load_json(path: str | Path) -> Any:
    """Read bounded UTF-8 JSON; reject duplicate fields and NaN/Infinity."""
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValidationError(f"{path}: file exceeds {MAX_FILE_BYTES:,} bytes")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise ValidationError(f"{path}: invalid UTF-8 JSON: {exc}") from exc


def _number(value: Any) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _integer(value: Any, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _matches(value: Any, kind: str) -> bool:
    if kind == "number":
        return _number(value)
    if kind == "boolean":
        return type(value) is bool
    return type(value) is str and len(value) <= 1000


def _keys(value: dict, required: set[str], optional: set[str], path: str, errors: list[str]) -> None:
    for key in sorted(required - value.keys()):
        errors.append(f"{path}: missing {key!r}")
    for key in sorted(value.keys() - required - optional):
        errors.append(f"{path}: unknown field {key!r}")


def validate(spec: Any) -> dict:
    """Return a validated spec, or fail before any playback or artifact writing.

    Times are explicit scene-relative milliseconds. Speech and motion may overlap
    each other, but a single channel cannot have competing actions. Branches are
    terminal scene steps, and the scene graph must be acyclic and reachable.
    """
    errors: list[str] = []
    if not isinstance(spec, dict):
        raise ValidationError("show: expected an object")
    _keys(spec, {"schema_version", "id", "title", "entry", "scenes"}, {"description", "events"}, "show", errors)
    if type(spec.get("schema_version")) is not int or spec["schema_version"] != 1:
        errors.append("show.schema_version: only integer version 1 is supported")
    if not isinstance(spec.get("id"), str) or not IDENTIFIER.fullmatch(spec["id"]):
        errors.append("show.id: use a lowercase identifier (letters, digits, hyphens, underscores)")
    if not isinstance(spec.get("title"), str) or not spec["title"].strip() or len(spec["title"]) > 160:
        errors.append("show.title: expected 1–160 nonblank characters")
    if "description" in spec and (not isinstance(spec["description"], str) or len(spec["description"]) > 2000):
        errors.append("show.description: expected text up to 2,000 characters")
    declared = spec.get("events", {})
    if not isinstance(declared, dict) or len(declared) > 64:
        errors.append("show.events: expected an object with at most 64 event declarations")
        declared = {}
    for name, kind in declared.items():
        if not isinstance(name, str) or not IDENTIFIER.fullmatch(name) or not isinstance(kind, str) or kind not in EVENT_TYPES:
            errors.append(f"show.events.{name}: use a valid identifier and boolean, number, or string")
    scenes = spec.get("scenes")
    if not isinstance(scenes, dict) or not 1 <= len(scenes) <= MAX_SCENES:
        raise ValidationError(errors + [f"show.scenes: expected 1–{MAX_SCENES} named scenes"])
    if not isinstance(spec.get("entry"), str) or spec["entry"] not in scenes:
        errors.append("show.entry: must refer to a defined scene")
    edges: dict[str, list[str]] = {}
    lengths: dict[str, int] = {}
    for scene_id, scene in scenes.items():
        base = f"scenes.{scene_id}"
        if not isinstance(scene_id, str) or not IDENTIFIER.fullmatch(scene_id):
            errors.append(f"{base}: invalid scene identifier")
        edges[scene_id] = []
        lengths[scene_id] = 0
        if not isinstance(scene, dict):
            errors.append(f"{base}: expected an object")
            continue
        _keys(scene, {"label", "steps"}, set(), base, errors)
        if not isinstance(scene.get("label"), str) or not scene["label"].strip() or len(scene["label"]) > 160:
            errors.append(f"{base}.label: expected 1–160 nonblank characters")
        steps = scene.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
            errors.append(f"{base}.steps: expected 1–{MAX_STEPS} steps")
            continue
        ids: set[str] = set()
        last_start = -1
        occupied = {"speech": [], "gesture": []}
        latest_end = 0
        for index, step in enumerate(steps):
            path = f"{base}.steps[{index}]"
            if not isinstance(step, dict):
                errors.append(f"{path}: expected an object")
                continue
            action_type = step.get("type")
            specific = {
                "speech": ({"duration_ms", "text"}, {"language"}),
                "gesture": ({"duration_ms", "name", "amplitude", "speed"}, set()),
                "wait": ({"duration_ms"}, set()),
                "branch": ({"event", "equals", "then", "else"}, set()),
            }
            if not isinstance(action_type, str) or action_type not in specific:
                errors.append(f"{path}.type: expected speech, gesture, wait, or branch")
                continue
            required, optional = specific[action_type]
            _keys(step, {"id", "type", "at_ms"} | required, optional, path, errors)
            step_id = step.get("id")
            if not isinstance(step_id, str) or not IDENTIFIER.fullmatch(step_id) or step_id in ids:
                errors.append(f"{path}.id: use a unique lowercase identifier within the scene")
            else:
                ids.add(step_id)
            start = step.get("at_ms")
            valid_start = _integer(start, 0, MAX_SCENE_MS)
            if not valid_start:
                errors.append(f"{path}.at_ms: expected integer milliseconds in 0..{MAX_SCENE_MS}")
            elif start < last_start:
                errors.append(f"{path}.at_ms: steps must be ordered by start time")
            else:
                last_start = start
            if action_type == "branch":
                if index != len(steps) - 1:
                    errors.append(f"{path}: branch must be the final step in its scene")
                if valid_start and start < latest_end:
                    errors.append(f"{path}: branch must wait until all scene actions finish ({latest_end} ms)")
                event = step.get("event")
                if not isinstance(event, str) or event not in declared:
                    errors.append(f"{path}.event: must refer to a declared event")
                elif isinstance(declared[event], str) and declared[event] in EVENT_TYPES and not _matches(step.get("equals"), declared[event]):
                    errors.append(f"{path}.equals: must match declared type {declared[event]}")
                for target in ("then", "else"):
                    if not isinstance(step.get(target), str) or step[target] not in scenes:
                        errors.append(f"{path}.{target}: must refer to a defined scene")
                    else:
                        edges[scene_id].append(step[target])
                if valid_start:
                    latest_end = max(latest_end, start)
                continue
            duration = step.get("duration_ms")
            valid_duration = _integer(duration, 1, 60_000)
            if not valid_duration:
                errors.append(f"{path}.duration_ms: expected integer milliseconds in 1..60000")
            if valid_start and valid_duration:
                end = start + duration
                if end > MAX_SCENE_MS:
                    errors.append(f"{path}: action ends beyond the scene duration limit")
                latest_end = max(latest_end, end)
                if action_type in occupied:
                    if any(start < other_end and other_start < end for other_start, other_end in occupied[action_type]):
                        errors.append(f"{path}: overlapping {action_type} actions compete for the same channel")
                    occupied[action_type].append((start, end))
            if action_type == "speech":
                if not isinstance(step.get("text"), str) or not step["text"].strip() or len(step["text"]) > 2000:
                    errors.append(f"{path}.text: expected 1–2,000 nonblank characters")
                if "language" in step and (not isinstance(step["language"], str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", step["language"])):
                    errors.append(f"{path}.language: expected a language tag such as zh-CN or en")
            if action_type == "gesture":
                if not isinstance(step.get("name"), str) or step["name"] not in GESTURES:
                    errors.append(f"{path}.name: unsupported semantic gesture; choose {', '.join(sorted(GESTURES))}")
                for parameter, minimum in (("amplitude", 0), ("speed", 0)):
                    value = step.get(parameter)
                    if not _number(value) or not minimum <= value <= 1 or (parameter == "speed" and value == 0):
                        errors.append(f"{path}.{parameter}: expected normalized {'0..1' if parameter == 'amplitude' else '>0..1'}")
        lengths[scene_id] = latest_end
    if errors:
        raise ValidationError(errors)
    visited: set[str] = set()
    visiting: set[str] = set()
    longest: dict[str, int] = {}

    def visit(scene_id: str) -> int:
        if scene_id in visiting:
            raise ValidationError(f"scene graph contains a cycle at {scene_id!r}; loops are not supported")
        if scene_id in visited:
            return longest[scene_id]
        visiting.add(scene_id)
        tail = max((visit(target) for target in edges[scene_id]), default=0)
        visiting.remove(scene_id)
        visited.add(scene_id)
        longest[scene_id] = lengths[scene_id] + tail
        return longest[scene_id]

    if visit(spec["entry"]) > MAX_SHOW_MS:
        raise ValidationError(f"show: longest route exceeds {MAX_SHOW_MS} ms")
    if set(scenes) != visited:
        raise ValidationError(f"show.scenes: unreachable scenes: {', '.join(sorted(set(scenes) - visited))}")
    return spec


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _label(step: dict) -> str:
    if step["type"] == "speech":
        return step["text"]
    if step["type"] == "gesture":
        return f"{step['name']} · amplitude {step['amplitude']} · speed {step['speed']}"
    if step["type"] == "branch":
        return f"{step['event']} == {json.dumps(step['equals'], ensure_ascii=False)}"
    return f"Wait {step['duration_ms']} ms"


class DryRunAdapter:
    """Semantic preview adapter; no SDK, network, speech synthesis, or motors."""

    name = "dry-run"

    def dispatch(self, command: dict) -> dict:
        return {"status": "simulated", "hardware_sent": False, "command_id": command["command_id"]}


def simulate(spec: dict, events: Any = None, *, mode: str = "dry-run") -> dict:
    validate(spec)
    if mode != "dry-run":
        raise ValidationError("Hardware playback is not implemented. No hardware connection or permission is configured; use --mode dry-run.")
    events = {} if events is None else events
    if not isinstance(events, dict):
        raise ValidationError("event fixture: expected an object")
    declared = spec.get("events", {})
    for name, value in events.items():
        if name not in declared:
            raise ValidationError(f"event fixture: undeclared event {name!r}")
        if not _matches(value, declared[name]):
            raise ValidationError(f"event fixture.{name}: expected {declared[name]}")
    events = dict(events)
    adapter = DryRunAdapter()
    timeline: list[dict] = []
    route: list[str] = []
    scene_id = spec["entry"]
    offset = 0
    previous_hash = "0" * 64
    while scene_id is not None:
        scene = spec["scenes"][scene_id]
        route.append(scene_id)
        next_scene = None
        scene_end = 0
        for step in scene["steps"]:
            duration = step.get("duration_ms", 0)
            start = offset + step["at_ms"]
            end = start + duration
            scene_end = max(scene_end, step["at_ms"] + duration)
            entry = {
                "index": len(timeline), "command_id": f"{scene_id}:{step['id']}",
                "scene_id": scene_id, "scene_label": scene["label"],
                "type": step["type"], "start_ms": start, "end_ms": end,
                "label": _label(step), "parameters": {key: value for key, value in step.items() if key not in {"id", "type", "at_ms"}},
            }
            if step["type"] == "branch":
                present = step["event"] in events
                matched = present and events[step["event"]] == step["equals"]
                next_scene = step["then"] if matched else step["else"]
                entry["decision"] = {"event": step["event"], "present": present,
                                     "observed": events.get(step["event"]), "matched": matched,
                                     "selected_scene": next_scene}
            entry["adapter_result"] = adapter.dispatch(entry)
            entry["previous_hash"] = previous_hash
            entry["hash"] = _hash(entry)
            previous_hash = entry["hash"]
            timeline.append(entry)
        offset += scene_end
        scene_id = next_scene
    result = {
        "format_version": 1, "show_id": spec["id"], "title": spec["title"],
        "mode": "dry-run", "hardware_sent": False,
        "source_sha256": _hash(spec), "events_sha256": _hash(events), "events": events,
        "route": route, "duration_ms": offset, "timeline": timeline,
        "final_hash": previous_hash,
        "integrity_note": "SHA256 checks detect accidental edits; this is not a signature or evidence of physical robot execution.",
    }
    result["manifest_hash"] = _hash(result)
    return result


def verify_audit(audit: Any) -> bool:
    """Check a saved dry-run artifact's checksum chain without executing it."""
    try:
        if not isinstance(audit, dict) or audit.get("format_version") != 1 or audit.get("mode") != "dry-run" or audit.get("hardware_sent") is not False:
            return False
        content = {key: value for key, value in audit.items() if key != "manifest_hash"}
        if _hash(content) != audit["manifest_hash"] or _hash(audit["events"]) != audit["events_sha256"]:
            return False
        previous = "0" * 64
        last_start = 0
        seen = set()
        if not isinstance(audit["timeline"], list) or not audit["timeline"]:
            return False
        for index, entry in enumerate(audit["timeline"]):
            data = {key: value for key, value in entry.items() if key != "hash"}
            if entry["index"] != index or entry["previous_hash"] != previous or _hash(data) != entry["hash"]:
                return False
            if not _integer(entry["start_ms"], last_start, MAX_SHOW_MS) or not _integer(entry["end_ms"], entry["start_ms"], MAX_SHOW_MS):
                return False
            if entry["command_id"] in seen or entry["adapter_result"]["status"] != "simulated" or entry["adapter_result"]["hardware_sent"] is not False:
                return False
            seen.add(entry["command_id"])
            last_start = entry["start_ms"]
            previous = entry["hash"]
        return previous == audit["final_hash"] and audit["duration_ms"] == max(entry["end_ms"] for entry in audit["timeline"])
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, RecursionError):
        return False


def render_svg(audit: dict) -> str:
    """Generate an escaped, self-contained SVG timeline with accessible labels."""
    colors = {"speech": "#69d7c5", "gesture": "#e8b56b", "wait": "#8f9fbf", "branch": "#bc9df4"}
    lanes = {"speech": 115, "gesture": 185, "wait": 255, "branch": 325}
    left, usable = 135, 920
    total = max(audit["duration_ms"], 1)
    # Keep the visible chart portable on systems without CJK fonts; preserve the
    # full authored title in the accessible SVG title and all JSON/text exports.
    display_title = audit["title"] if audit["title"].isascii() else audit["show_id"].replace("-", " ").replace("_", " ").title()
    display_title = display_title if len(display_title) <= 65 else display_title[:62] + "..."
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 435" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(audit["title"])} — dry-run timeline</title>',
        f'<desc id="desc">Simulated speech, gestures, waits and event decisions across {audit["duration_ms"] / 1000:g} seconds. No hardware commands were sent.</desc>',
        '<style>text{font-family:system-ui,"Noto Sans CJK SC",sans-serif} .small{font-size:12px;fill:#a9b9c9}.label{font-size:13px;fill:#e8eff7}</style>',
        '<rect width="1100" height="435" rx="12" fill="#101a29"/>',
        f'<text x="30" y="37" font-size="24" fill="#f1f6fc">{html.escape(display_title)}</text>',
        '<text x="30" y="65" class="small">AIMA STORY DIRECTOR / DRY-RUN / NO HARDWARE COMMANDS</text>',
    ]
    for tick in range(11):
        x = left + usable * tick / 10
        elements.extend([f'<path d="M{x:g} 95V365" stroke="#26364b"/>', f'<text x="{x:g}" y="390" text-anchor="middle" class="small">{total * tick / 10000:g}s</text>'])
    for lane, y in lanes.items():
        elements.extend([f'<text x="30" y="{y + 20}" class="label">{lane.upper()}</text>', f'<path d="M{left} {y + 42}H1055" stroke="#26364b"/>'])
    for entry in audit["timeline"]:
        x = left + usable * entry["start_ms"] / total
        y = lanes[entry["type"]]
        bar_width = max(5, usable * (entry["end_ms"] - entry["start_ms"]) / total)
        title = html.escape(f"{entry['command_id']} | {entry['start_ms']}–{entry['end_ms']} ms | {entry['label']}")
        label = html.escape(entry["command_id"])
        elements.append(f'<g><title>{title}</title><rect x="{x:g}" y="{y}" width="{bar_width:g}" height="30" rx="4" fill="{colors[entry["type"]]}" opacity=".85"/>')
        if bar_width > 85:
            short_label = label if len(label) <= int(bar_width / 7) else html.escape(entry["parameters"].get("name", entry["type"]))
            elements.append(f'<text x="{x + 7:g}" y="{y + 20}" font-size="11" fill="#101a29">{short_label}</text>')
        elements.append('</g>')
    route = html.escape(" → ".join(audit["route"]))
    elements.extend([f'<text x="30" y="423" class="small">Route: {route}</text>', '</svg>'])
    return "\n".join(elements) + "\n"


def execution_checklist(audit: dict) -> str:
    lines = [f"# {audit['title']} — execution preparation", "", "**Mode: dry-run. Hardware commands sent: 0.**", "",
             "This is a planning artifact. A robot adapter, an authorized device connection, and verified device resources are not provided.", "",
             "## Before any separately implemented hardware deployment", "",
             "- [ ] Select the exact robot model, firmware, and matching vendor protocol documentation.",
             "- [ ] Obtain authorized device access and map semantic gestures to supported device resources.",
             "- [ ] Validate speech duration and motion completion against device acknowledgements; these timings are authored estimates.",
             "- [ ] Supply live event sources; this preview uses a fixed event fixture, not robot sensors.",
             "- [ ] Test interruption, stop, disconnect, resource conflicts, and operator control on the actual device.",
             "- [ ] Review the venue and device operating requirements with the responsible operator.", "",
             "## Selected route", "", " → ".join(audit["route"]), "", "## Command plan", "",
             "| Start ms | End ms | Command | Type | Planned content |", "| ---: | ---: | --- | --- | --- |"]
    for entry in audit["timeline"]:
        label = entry["label"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {entry['start_ms']} | {entry['end_ms']} | {entry['command_id']} | {entry['type']} | {label} |")
    lines.extend(["", "## Integrity", "", f"Source SHA256: `{audit['source_sha256']}`", f"Artifact manifest SHA256: `{audit['manifest_hash']}`", "", audit["integrity_note"], ""])
    return "\n".join(lines)


def write_artifacts(audit: dict, output: str | Path) -> list[Path]:
    if not verify_audit(audit):
        raise ValidationError("Cannot export: audit integrity verification failed")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "timeline.json": json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        "timeline.svg": render_svg(audit),
        "execution-checklist.md": execution_checklist(audit),
        "transcript.txt": "\n".join(f"[{entry['start_ms'] / 1000:07.3f}s] {entry['parameters']['text']}" for entry in audit["timeline"] if entry["type"] == "speech") + "\n",
    }
    paths = []
    for name, content in files.items():
        path = output / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths
