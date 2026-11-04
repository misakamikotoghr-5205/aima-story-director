"""Reproduce local tests and all example workflows without external dependencies."""

from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main():
    run("-m", "unittest", "discover", "-s", "tests", "-v")
    with tempfile.TemporaryDirectory(prefix="aima-director-check-") as temporary:
        for name in ("welcome", "exhibition", "distance-reminder"):
            destination = str(Path(temporary) / name)
            run("-m", "aima_director", "validate", f"examples/{name}.json")
            run("-m", "aima_director", "simulate", f"examples/{name}.json", "--events", f"examples/{name}.events.json", "--out", destination)
            run("-m", "aima_director", "verify", str(Path(destination) / "timeline.json"))
    print("All local checks passed; all playback remained dry-run.")


if __name__ == "__main__":
    main()
