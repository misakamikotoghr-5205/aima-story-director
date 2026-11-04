"""Command-line entry point: python -m aima_director."""

import argparse
import sys

from . import ValidationError, __version__, load_json, simulate, validate, verify_audit, write_artifacts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate and rehearse robot-show scripts offline. Dry-run only; no robot connection.")
    parser.add_argument("--version", action="version", version=f"aima-story-director {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate", help="Validate a JSON show, including all branch paths")
    check.add_argument("show")
    play = sub.add_parser("simulate", help="Create an auditable timeline, SVG, transcript, and checklist")
    play.add_argument("show")
    play.add_argument("--events", help="Path to a JSON event fixture (missing events take the else route)")
    play.add_argument("--out", default="output", help="Output directory, default: output")
    play.add_argument("--mode", default="dry-run", help="Only dry-run is implemented; hardware mode fails without sending commands")
    audit = sub.add_parser("verify", help="Check a timeline JSON artifact's integrity hashes")
    audit.add_argument("timeline")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            spec = validate(load_json(args.show))
            print(f"VALID: {spec['title']} ({len(spec['scenes'])} scenes); all routes checked")
        elif args.command == "simulate":
            spec = load_json(args.show)
            events = load_json(args.events) if args.events else {}
            result = simulate(spec, events, mode=args.mode)
            paths = write_artifacts(result, args.out)
            print(f"DRY-RUN: {result['title']} | {result['duration_ms'] / 1000:g}s | {' -> '.join(result['route'])}")
            print(f"{len(result['timeline'])} simulated commands; hardware commands sent: 0")
            for path in paths:
                print(path)
        else:
            if not verify_audit(load_json(args.timeline)):
                raise ValidationError("Audit verification FAILED: invalid artifact or changed content")
            print("Audit integrity verified. This does not prove physical robot execution.")
    except (ValidationError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
