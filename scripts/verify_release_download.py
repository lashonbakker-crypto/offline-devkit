"""Verify downloaded release assets against source, then exercise the archive.

No asset download or rebuild is performed here. Use assets and source from
the same release. --source-ref optionally exports a local Git ref with LF
line endings. All CLI probes run outside the source directory.
"""

import argparse
import gzip
import hashlib
import io
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


def export_release_source(repository: Path, destination: Path, ref: str) -> None:
    """Export a local ref without inheriting Windows newline conversion.

    The per-command settings do not change the user's Git configuration.
    The caller provides an empty, temporary destination directory.
    """
    require(bool(ref) and not ref.startswith("-"), "expected a local Git ref")
    data = subprocess.check_output(
        [
            "git", "-C", str(repository), "-c", "core.autocrlf=false",
            "-c", "core.eol=lf", "archive", "--format=zip", ref,
        ],
        stderr=subprocess.PIPE,
    )
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        source.extractall(destination)


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


def exercise_input_errors(archive: Path, work: Path, version: str, gzip_supported: bool) -> None:
    """Check the v0.4.1 input-error contract without imposing it on old releases."""
    matched = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", version)
    require(matched is not None, "expected a numeric major.minor.patch version")
    if tuple(map(int, matched.groups())) < (0, 4, 1):
        return
    # A fresh temporary name avoids depending on a real account or home path.
    # Windows may expand ~user to a missing profile rather than reject lookup;
    # either case must remain a controlled input error.
    missing_home = f"~offline_devkit_missing_home_{work.name}/records.jsonl"
    cases = [([command, missing_home, "--check" if command == "json" else "--json"], b"")
             for command in ("json", "jsonl", "dupes", "sizes")]
    inputs = [(work / "records.jsonl", [])]
    if gzip_supported:
        inputs.append((work / "valid.jsonl.gz", ["--gzip"]))
    for path, options in inputs:
        for from_file in (True, False):
            cases.append((
                ["jsonl", str(path) if from_file else "-", *options,
                 "--json", "--max-line-bytes", str(sys.maxsize)],
                b"" if from_file else path.read_bytes(),
            ))
    for arguments, data in cases:
        result = subprocess.run(
            [sys.executable, "-I", str(archive), *arguments],
            cwd=work, input=data, capture_output=True, timeout=15,
        )
        require(result.returncode == 2, f"unexpected input-error exit {result.returncode}: {arguments}")
        require(not result.stdout, f"input error produced a success report: {arguments}")
        require(bool(result.stderr) and b"Traceback" not in result.stderr, f"missing or uncontrolled input error: {arguments}")
    print("Input errors OK: unresolved home paths and oversized JSONL limits return 2 without reports or tracebacks", flush=True)


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
        gzip_supported = "--gzip" in run(["jsonl", "--help"]).decode("utf-8")
        gzip_cases = []
        if gzip_supported:
            valid = gzip.compress((work / "records.jsonl").read_bytes(), mtime=0)
            invalid = gzip.compress((work / "invalid-records.jsonl").read_bytes(), mtime=0)
            bad_crc = bytearray(valid)
            bad_crc[-8] ^= 1
            for name, data, code, complete in (
                ("valid.jsonl.gz", valid, 0, True),
                ("invalid.jsonl.gz", invalid, 2, True),
                ("truncated.jsonl.gz", valid[:-4], 2, False),
                ("bad-crc.jsonl.gz", bytes(bad_crc), 2, False),
            ):
                path = work / name
                path.write_bytes(data)
                gzip_cases.append((path, data, code, complete))
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
        if gzip_supported:
            for path, data, code, complete in gzip_cases:
                for file_input in (True, False):
                    arguments = ["jsonl", str(path) if file_input else "-", "--gzip", "--json"]
                    report = json.loads(run(arguments, b"" if file_input else data, code))
                    require(report["complete"] is complete, "gzip completeness changed")
                    if not complete:
                        require(bool(report["read_error"]), "missing gzip read error")
                    elif code == 0:
                        require(report["valid_lines"] == 3 and report["invalid_lines"] == 0, "gzip valid counts changed")
                    else:
                        require([item["line"] for item in report["errors"]] == [2, 3], "gzip physical line numbers changed")
            compressed = gzip.compress(b'"' + b"x" * 200000 + b'"\n{}\n', mtime=0)
            report = json.loads(run(["jsonl", "--gzip", "--json", "--max-line-bytes", "8", "--max-errors", "0"], compressed, 2))
            require(report["complete"] and (report["lines_checked"], report["valid_lines"], report["invalid_lines"], report["errors_omitted"]) == (2, 1, 1, 1), "decompressed record limits changed")
            print("Gzip JSONL OK: file/binary stdin, record limits, CRC and truncation exit 2", flush=True)
        exercise_input_errors(archive, work, version, gzip_supported)
        after = {path: path.read_bytes() for path in work.rglob("*") if path.is_file()}
        require(before == after, "fixture files changed")
        print("JSONL OK: valid/invalid counts, physical line numbers and exit 2", flush=True)
        print("Read-only checks OK; downloaded archive passed isolated execution", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("download_directory", type=Path)
    parser.add_argument("--source-directory", type=Path, default=ROOT)
    parser.add_argument("--source-ref", help="export this local Git ref from the source directory; requires Git")
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    try:
        def verify(source: Path) -> None:
            archive = verify_assets(args.download_directory.resolve(), source)
            exercise_archive(archive, source, args.expected_version)

        if args.source_ref is None:
            verify(args.source_directory.resolve())
        else:
            with tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary)
                export_release_source(args.source_directory.resolve(), source, args.source_ref)
                verify(source)
    except (OSError, ValueError, UnicodeError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        parser.exit(2, f"verification failed: {error}\n")


if __name__ == "__main__":
    main()
