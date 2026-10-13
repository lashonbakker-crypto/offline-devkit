"""Verify the published recipes on an actual Bash or PowerShell executable."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def example_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ROOT / "examples").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", choices=["bash", "powershell"], required=True)
    args = parser.parse_args()
    executable = shutil.which("bash" if args.shell == "bash" else "pwsh")
    if executable is None:
        raise SystemExit(f"Required shell is not installed: {args.shell}")
    if args.shell == "bash":
        version_command = [executable, "--version"]
    else:
        version_command = [executable, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"]
    version = subprocess.check_output(version_command, text=True, encoding="utf-8").splitlines()[0]
    print(f"Shell: {version}; Python: {sys.version.split()[0]}", flush=True)
    before = example_hashes()
    cases = [
        ("valid", 0, 4, 4, 0, 0, 0),
        ("invalid", 2, 4, 3, 1, 0, 2),
        ("producer-failure", 3, 2, 2, 0, 3, 0),
    ]
    for mode, code, lines, valid, invalid, producer, validator in cases:
        if args.shell == "bash":
            import os

            environment = dict(os.environ, DEVKIT_PYTHON=sys.executable)
            command = [executable, "scripts/check_jsonl_pipeline.sh", mode]
        else:
            environment = None
            command = [executable, "-NoProfile", "-File", "scripts/check_jsonl_pipeline.ps1", "-Mode", mode, "-Python", sys.executable]
        process = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=30)
        assert process.returncode == code, (mode, process.returncode, process.stderr.decode("utf-8", errors="replace"))
        report = json.loads(process.stdout.decode("utf-8"))
        assert (report["lines_checked"], report["valid_lines"], report["invalid_lines"]) == (lines, valid, invalid), (mode, report)
        assert report["complete"] is True and report["read_error"] is None, (mode, report)
        assert report["errors_omitted"] == 0, (mode, report)
        if mode == "invalid":
            # A literal UTF-8 key and its escaped equivalent must reach the validator unchanged.
            assert report["errors"] == [{"line": 2, "message": "duplicate object key: '城市'"}], report
        else:
            assert report["errors"] == [], (mode, report)
        assert f"producer_exit={producer} validator_exit={validator}" in process.stderr.decode("utf-8"), (mode, process.stderr)
        print(f"{mode}: exit={code}; lines={lines}; valid={valid}; invalid={invalid}; producer={producer}; validator={validator}", flush=True)
    assert before == example_hashes(), "Example files changed"
    print("All three pipeline cases passed; UTF-8 duplicate key verified; example hashes unchanged.")


if __name__ == "__main__":
    main()
