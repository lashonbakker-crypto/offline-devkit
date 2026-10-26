"""Verify the copied consumer CI recipe with the pinned, published archive."""

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "examples" / "github-actions"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="existing published v0.4.0 pyz; otherwise download once")
    args = parser.parse_args()
    try:
        # Download once using the recipe's own bounded checksum verifier.
        # Each subprocess independently rechecks the cached bytes.
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location("consumer_jsonl_recipe", RECIPE / "check_jsonl.py")
        recipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recipe)
        data = recipe.archive_bytes(args.archive.expanduser() if args.archive is not None else None)
        with tempfile.TemporaryDirectory(prefix="devkit-consumer-test-") as temporary:
            work = Path(temporary)
            scripts = work / ".github" / "scripts"
            workflows = work / ".github" / "workflows"
            scripts.mkdir(parents=True)
            workflows.mkdir(parents=True)
            helper = scripts / "check_jsonl.py"
            workflow = workflows / "check-jsonl.yml"
            shutil.copyfile(RECIPE / "check_jsonl.py", helper)
            shutil.copyfile(RECIPE / "check-jsonl.yml", workflow)
            archive = work / "trusted tool.pyz"
            archive.write_bytes(data)
            dataset = work / "data"
            dataset.mkdir()
            valid = b'{"id":1}\n{"id":2,"score":1E-400}\n{"id":3}\n'
            fixtures = {
                dataset / "valid records.jsonl": valid,
                dataset / "records.jsonl.gz": gzip.compress(valid, mtime=0),
                dataset / "duplicate.jsonl": b'{"id":1}\n{"id":2,"\\u0069d":3}\n{"id":3}\n',
                dataset / "truncated.jsonl.gz": gzip.compress(valid, mtime=0)[:-4],
            }
            originals = {}
            for path, content in fixtures.items():
                path.write_bytes(content)
                originals[path] = hashlib.sha256(content).hexdigest()
            # The recipe has one literal run command. Execute that command
            # with this interpreter and the default dataset, outside source.
            commands = [line.strip()[5:].strip() for line in workflow.read_text(encoding="utf-8").splitlines() if line.strip().startswith("run:")]
            if len(commands) != 1:
                raise RuntimeError("expected exactly one literal recipe run command")
            command = shlex.split(commands[0])
            if not command or command[0] != "python":
                raise RuntimeError("expected the documented Python recipe command")
            command[0] = sys.executable

            def invoke(label, arguments, status, *, complete=None, counts=None):
                result = subprocess.run(arguments, cwd=work, capture_output=True, timeout=45, check=False)
                if result.returncode != status:
                    raise RuntimeError(f"{label}: expected exit {status}; got {result.returncode}; stderr={result.stderr!r}")
                if complete is not None:
                    report = json.loads(result.stdout)
                    if result.stderr or report["complete"] is not complete:
                        raise RuntimeError(f"{label}: unexpected report or stderr: {report}, {result.stderr!r}")
                    if report["lines_checked"] != report["valid_lines"] + report["invalid_lines"]:
                        raise RuntimeError(f"{label}: inconsistent record counters")
                    if counts is not None and (report["valid_lines"], report["invalid_lines"]) != counts:
                        raise RuntimeError(f"{label}: unexpected counts: {report}")
                    if label == "duplicate-key" and report["errors"] != [{"line": 2, "message": "duplicate object key: 'id'"}]:
                        raise RuntimeError(f"{label}: wrong error location: {report}")
                    if not complete and not report["read_error"]:
                        raise RuntimeError(f"{label}: missing incomplete-read explanation")
                    if complete and report["read_error"] is not None:
                        raise RuntimeError(f"{label}: unexpected read error")
                elif result.stdout or not result.stderr:
                    raise RuntimeError(f"{label}: expected stderr and empty stdout")
                print(f"{label}: exit={result.returncode}" + (f"; complete={str(complete).lower()}" if complete is not None else ""))
                return result

            invoke("copied-workflow-gzip", [*command, "--archive", str(archive)], 0, complete=True, counts=(3, 0))
            base = [sys.executable, "-B", str(helper)]
            cached = ["--archive", str(archive)]
            invoke("plain-jsonl", [*base, str(dataset / "valid records.jsonl"), *cached], 0, complete=True, counts=(3, 0))
            invoke("duplicate-key", [*base, str(dataset / "duplicate.jsonl"), *cached], 2, complete=True, counts=(2, 1))
            invoke("truncated-gzip", [*base, str(dataset / "truncated.jsonl.gz"), "--gzip", *cached], 2, complete=False)
            invoke("missing-input", [*base, str(dataset / "missing.jsonl"), *cached], 2)
            marker = work / "untrusted-code-executed"
            untrusted = work / "untrusted tool.pyz"
            untrusted.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nraise SystemExit(2)\n", encoding="utf-8")
            rejected = invoke("wrong-checksum", [*base, str(dataset / "valid records.jsonl"), "--archive", str(untrusted)], 2)
            if b"SHA-256 mismatch" not in rejected.stderr or marker.exists():
                raise RuntimeError("untrusted archive was not rejected before execution")
            oversized = work / "oversized.pyz"
            oversized.write_bytes(b"x" * (recipe.MAX_ARCHIVE_BYTES + 1))
            rejected = invoke("oversized-tool", [*base, str(dataset / "valid records.jsonl"), "--archive", str(oversized)], 2)
            if b"size limit" not in rejected.stderr:
                raise RuntimeError("archive size guard was not reported")
            for path, digest in originals.items():
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise RuntimeError(f"dataset changed: {path.name}")
            if sorted(path.name for path in dataset.iterdir()) != sorted(path.name for path in originals):
                raise RuntimeError("unexpected output created beside dataset inputs")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print("All seven consumer recipe cases passed; dataset hashes unchanged; untrusted code was not executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
