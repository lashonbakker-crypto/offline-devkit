"""Try three real JSONL checks using disposable, synthetic sample files."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="use an existing, trusted pyz instead of source")
    args = parser.parse_args()
    command = [sys.executable, "-B", "-m", "offline_devkit"]
    if args.archive is not None:
        archive = args.archive.resolve()
        if not archive.is_file():
            parser.error("--archive must point to an existing pyz file")
        command = [sys.executable, "-I", "-B", str(archive)]
    valid = '{"id":1,"城市":"南京"}\n{"id":2,"score":1E-400}\n{"id":3}\n'.encode("utf-8")
    compressed = gzip.compress(valid, mtime=0)
    duplicate = b'{"id":1}\n{"id":2,"\\u0069d":3}\n{"id":3}\n'
    cases = [
        ("valid-gzip", "valid.jsonl.gz", compressed, True, 0, True),
        ("duplicate-key", "duplicate.jsonl", duplicate, False, 2, True),
        ("truncated-gzip", "truncated.jsonl.gz", compressed[:-4], True, 2, False),
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="offline-devkit-demo-") as temporary:
            work = Path(temporary)
            originals = {}
            for _, name, data, _, _, _ in cases:
                (work / name).write_bytes(data)
                originals[name] = hashlib.sha256(data).hexdigest()
            for index, (label, name, _, is_gzip, status, complete) in enumerate(cases, start=1):
                options = ["--gzip"] if is_gzip else []
                result = subprocess.run(
                    [*command, "jsonl", str(work / name), *options, "--json"],
                    stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
                    cwd=work if args.archive is not None else ROOT, check=False,
                )
                if result.returncode != status or result.stderr:
                    raise RuntimeError(f"{label}: expected exit {status}; got {result.returncode}; stderr={result.stderr!r}")
                report = json.loads(result.stdout)
                if report["complete"] is not complete:
                    raise RuntimeError(f"{label}: unexpected completeness: {report}")
                if report["lines_checked"] != report["valid_lines"] + report["invalid_lines"]:
                    raise RuntimeError(f"{label}: inconsistent counters: {report}")
                if complete:
                    expected = (3, 3, 0) if status == 0 else (3, 2, 1)
                    actual = (report["lines_checked"], report["valid_lines"], report["invalid_lines"])
                    errors = [] if status == 0 else [{"line": 2, "message": "duplicate object key: 'id'"}]
                    if actual != expected or report["errors"] != errors or report["read_error"] is not None:
                        raise RuntimeError(f"{label}: unexpected validation result: {report}")
                elif not report["read_error"] or report["invalid_lines"]:
                    raise RuntimeError(f"{label}: missing read error or unexpected invalid record: {report}")
                print(f"[{index}/3] {label}: exit={result.returncode}; valid={report['valid_lines']}; invalid={report['invalid_lines']}; complete={str(complete).lower()}")
                for error in report["errors"]:
                    print(f"      line {error['line']}: {error['message']}")
                if not complete:
                    print("      The gzip stream is incomplete; any counts above are partial.")
            actual_files = sorted(path.name for path in work.iterdir())
            if actual_files != sorted(originals):
                raise RuntimeError("unexpected files created beside the inputs")
            for name, expected_hash in originals.items():
                if hashlib.sha256((work / name).read_bytes()).hexdigest() != expected_hash:
                    raise RuntimeError(f"input sample changed: {name}")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print("Demo passed: all three expected outcomes verified; sample files unchanged; no extracted files created.")
    print("The demo exits 0 because both bad inputs were correctly rejected with exit 2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
