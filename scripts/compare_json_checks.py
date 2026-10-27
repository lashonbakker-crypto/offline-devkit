"""Compare Python's default JSON settings with real offline-devkit commands."""

import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMMAND = [sys.executable, "-B", "-m", "offline_devkit"]


def run_cli(*arguments: str, expected_status: int) -> str:
    result = subprocess.run(
        [*COMMAND, *arguments], stdin=subprocess.DEVNULL, capture_output=True,
        timeout=30, cwd=ROOT, check=False,
    )
    if result.returncode != expected_status or result.stderr:
        raise RuntimeError(
            f"CLI {arguments[0]}: expected exit {expected_status}; "
            f"got {result.returncode}; stderr={result.stderr!r}"
        )
    return result.stdout.decode("utf-8")


def number_tokens(text: str) -> dict[str, str]:
    # Only the synthetic flat numeric object is used here. These callbacks
    # inspect spelling without depending on any particular float output tail.
    return json.loads(text, parse_int=str, parse_float=str)


def main() -> int:
    duplicate = '{"id":1,"\\u0069d":2}\n'
    nonfinite = '{"score":NaN}\n'
    numbers = '{"ratio":0.123456789012345678901,"tiny":1E-400,"zero":-0}\n'
    samples = {
        "duplicate.jsonl": duplicate,
        "nonfinite.jsonl": nonfinite,
        "numbers.json": numbers,
    }
    try:
        print(f"Python: {platform.python_implementation()} {platform.python_version()}")
        print(f"Tool: {run_cli('--version', expected_status=0).strip()}")
        print("Baseline: json.loads(text), then json.dumps(value), with default settings.")
        print("Scope: a settings comparison, not a speed or schema-validation comparison.")
        with tempfile.TemporaryDirectory(prefix="offline-devkit-compare-") as temporary:
            work = Path(temporary)
            hashes = {}
            for name, text in samples.items():
                data = text.encode("utf-8")
                (work / name).write_bytes(data)
                hashes[name] = hashlib.sha256(data).hexdigest()

            cases = [
                ("escaped duplicate key", "duplicate.jsonl", "duplicate object key: 'id'"),
                ("non-standard NaN", "nonfinite.jsonl", "non-standard JSON number: NaN"),
            ]
            for index, (label, name, error_message) in enumerate(cases, start=1):
                source = (work / name).read_text(encoding="utf-8")
                value = json.loads(source)
                baseline = json.dumps(value)
                if name == "duplicate.jsonl" and value != {"id": 2}:
                    raise RuntimeError("default decoder did not retain only the last duplicate value")
                if name == "nonfinite.jsonl" and not math.isnan(value["score"]):
                    raise RuntimeError("default decoder did not accept NaN")
                actual = run_cli("jsonl", str(work / name), "--json", expected_status=2)
                report = json.loads(actual)
                expected = {
                    "lines_checked": 1, "valid_lines": 0, "invalid_lines": 1,
                    "errors": [{"line": 1, "message": error_message}],
                    "errors_omitted": 0, "complete": True, "read_error": None,
                }
                if report != expected:
                    raise RuntimeError(f"{label}: unexpected strict report: {report}")
                print(f"\n[{index}/3] {label}")
                print(f"Input: {source.rstrip()}")
                print(f"Python defaults: accepted; json.dumps -> {baseline}")
                print("offline-devkit jsonl --json: exit=2; actual stdout:")
                print(actual, end="")

            source = (work / "numbers.json").read_text(encoding="utf-8")
            baseline = json.dumps(json.loads(source))
            original_tokens = number_tokens(source)
            baseline_tokens = number_tokens(baseline)
            if set(original_tokens) != set(baseline_tokens) or not all(
                original_tokens[key] != baseline_tokens[key] for key in original_tokens
            ):
                raise RuntimeError("the numeric sample did not demonstrate all three spelling changes")
            actual = run_cli("json", str(work / "numbers.json"), "--compact", expected_status=0)
            if actual != source:
                raise RuntimeError("strict formatter did not preserve the sample's numeric tokens")
            print("\n[3/3] numeric spelling during formatting")
            print(f"Input: {source.rstrip()}")
            print(f"Python defaults: json.dumps -> {baseline}")
            print("offline-devkit json --compact: exit=0; actual stdout:")
            print(actual, end="")

            if sorted(path.name for path in work.iterdir()) != sorted(samples):
                raise RuntimeError("unexpected files created beside the samples")
            for name, expected_hash in hashes.items():
                if hashlib.sha256((work / name).read_bytes()).hexdigest() != expected_hash:
                    raise RuntimeError(f"input sample changed: {name}")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print("\nComparison passed: all three differences verified; sample files unchanged; temporary files cleaned.")
    print("Python can implement strict policies using hooks; these are comparisons with its defaults.")
    print("Preserving number spelling does not provide decimal arithmetic or validate application schemas.")
    print("The script exits 0 because the two invalid samples were correctly rejected with exit 2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
