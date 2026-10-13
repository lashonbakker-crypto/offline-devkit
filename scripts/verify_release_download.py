"""Verify downloaded release assets against source, then exercise the archive.

No download or build is performed here. Use assets and source from the same
release. All CLI probes run with isolated Python outside the source directory.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINT = b"from offline_devkit.cli import main\n\nraise SystemExit(main())\n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_assets(download: Path, source: Path) -> Path:
    archive = download / "offline-devkit.pyz"
    fields = (download / "SHA256SUMS.txt").read_text(encoding="utf-8").split()
    require(
        len(fields) == 2
        and re.fullmatch(r"[0-9a-f]{64}", fields[0]) is not None
        and fields[1] == archive.name,
        "expected one SHA-256 entry for offline-devkit.pyz",
    )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    require(digest == fields[0], "SHA-256 MISMATCH; archive was not executed")
    print(f"SHA-256 OK: {digest}", flush=True)
    expected = {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in sorted((source / "offline_devkit").glob("*.py"))
    }
    require(bool(expected), "source directory has no offline_devkit Python modules")
    expected["LICENSE"] = (source / "LICENSE").read_bytes()
    expected["__main__.py"] = ENTRY_POINT
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        require(len(names) == len(set(names)), "archive contains duplicate entries")
        files = {item.filename for item in package.infolist() if not item.is_dir()}
        require(files == set(expected), "archive file list differs from release source")
        for name, content in expected.items():
            require(package.read(name) == content, f"source bytes differ: {name}")
    print(f"Source bytes OK: {len(expected) - 2} modules, entry point and license", flush=True)
    return archive.resolve()


def exercise_archive(archive: Path, source: Path, version: str) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)

        def run(arguments: list[str], data: bytes = b"", code: int = 0) -> bytes:
            result = subprocess.run(
                [sys.executable, "-I", str(archive), *arguments],
                cwd=work, input=data, capture_output=True, timeout=15,
            )
            require(result.returncode == code, f"unexpected exit {result.returncode}: {arguments}")
            require(b"Traceback" not in result.stderr, f"uncontrolled error: {arguments}")
            if code == 0:
                require(not result.stderr, f"unexpected stderr: {arguments}")
            return result.stdout

        require(
            run(["--version"]).decode("utf-8").strip() == f"offline-devkit {version}",
            "archive version differs from expected release",
        )
        payload = b'{"number":1E-400,"integer":9007199254740993,"zero":-0,"decimal":0.12345678901234567890}'
        input_file = work / "input.json"
        for boms in range(4):
            data = b"\xef\xbb\xbf" * boms + payload
            input_file.write_bytes(data)
            for from_file in (False, True):
                for check in (False, True):
                    arguments = ["json", str(input_file) if from_file else "-", "--check" if check else "--compact"]
                    output = run(arguments, b"" if from_file else data, 0 if boms < 2 else 2)
                    require(output == (payload + b"\n" if boms < 2 and not check else b""), "JSON numeric tokens or BOM behavior changed")
            require(input_file.read_bytes() == data, "JSON input file changed")
        print("JSON OK: exact numbers and 16 BOM/file/stdin/check/format cases", flush=True)

        fixtures = work / "fixtures"
        shutil.copytree(source / "examples" / "files", fixtures)
        for name in ("records.jsonl", "invalid-records.jsonl"):
            shutil.copyfile(source / "examples" / name, work / name)
        before = {path: path.read_bytes() for path in work.rglob("*") if path.is_file()}
        for verify in (False, True):
            arguments = ["dupes", str(fixtures), "--json"]
            if verify:
                arguments.append("--verify-bytes")
            report = json.loads(run(arguments))
            require(report["errors"] == [] and len(report["groups"]) == 1, "duplicate fixture result changed")
            require(report["groups"][0]["paths"] == ["copies/note-copy.txt", "note.txt"], "duplicate paths changed")
            require(report["verify_bytes"] is verify, "verification mode changed")
            require(report["byte_comparisons"] == int(verify), "comparison count changed")
            require(report["groups"][0]["verified_by"] == ("bytes" if verify else "sha256"), "group evidence changed")
        run(["dupes", str(fixtures), "--verify-bytes", "--fail-if-found", "--json"], code=1)
        sizes = json.loads(run(["sizes", str(fixtures), "--top", "3", "--json"]))
        require(sizes["errors"] == [] and sizes["total_bytes"] == 187, "size fixture result changed")
        print("File reports OK: hash/byte modes, duplicate exit 1 and logical sizes", flush=True)
        for name, lines, valid, invalid in (("records.jsonl", 3, 3, 0), ("invalid-records.jsonl", 4, 2, 2)):
            report = json.loads(run(["jsonl", str(work / name), "--json"], code=2 if invalid else 0))
            require(
                report["complete"] and report["read_error"] is None
                and (report["lines_checked"], report["valid_lines"], report["invalid_lines"]) == (lines, valid, invalid),
                "JSONL counts changed",
            )
            if invalid:
                require([item["line"] for item in report["errors"]] == [2, 3], "JSONL error lines changed")
        after = {path: path.read_bytes() for path in work.rglob("*") if path.is_file()}
        require(before == after, "fixture files changed")
        print("JSONL OK: valid/invalid counts, physical line numbers and exit 2", flush=True)
        print("Read-only checks OK; downloaded archive passed isolated execution", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("download_directory", type=Path)
    parser.add_argument("--source-directory", type=Path, default=ROOT)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    try:
        archive = verify_assets(args.download_directory.resolve(), args.source_directory.resolve())
        exercise_archive(archive, args.source_directory.resolve(), args.expected_version)
    except (OSError, ValueError, UnicodeError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        parser.exit(2, f"verification failed: {error}\n")


if __name__ == "__main__":
    main()
