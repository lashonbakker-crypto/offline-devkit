"""Console entry point. All commands are read-only and run locally."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .files import duplicate_report, scan_directory, size_report
from .json_tools import JsonError, format_json, parse_json
from .jsonl_tools import DEFAULT_MAX_ERRORS, DEFAULT_MAX_LINE_BYTES, validate_jsonl

MAX_JSON_BYTES = 16 * 1024 * 1024


def _non_negative(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if number < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return number


def _positive(value: str) -> int:
    number = _non_negative(value)
    if not number:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="offline-devkit",
        description="Read-only local tools for JSON, JSON Lines, duplicate files, and directory sizes.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    formatter = commands.add_parser("json", help="validate or format strict JSON without rounding numbers")
    formatter.add_argument("file", nargs="?", default="-", help="UTF-8 input file; - means stdin")
    formatter.add_argument("--check", action="store_true", help="validate only; emit no output")
    formatter.add_argument("--sort-keys", action="store_true", help="sort object keys")
    formatter.add_argument("--compact", action="store_true", help="remove insignificant whitespace")
    formatter.add_argument("--indent", type=int, choices=(2, 4), default=2)

    lines = commands.add_parser("jsonl", help="validate JSON Lines with line-numbered errors and bounded reads")
    lines.add_argument("file", nargs="?", default="-", help="UTF-8 JSONL/NDJSON file; - means stdin")
    lines.add_argument("--json", action="store_true", dest="as_json", help="emit a machine-readable validation report")
    lines.add_argument("--max-line-bytes", type=_positive, default=DEFAULT_MAX_LINE_BYTES, metavar="BYTES", help="record byte limit excluding LF/CRLF; default 1048576")
    lines.add_argument("--max-errors", type=_non_negative, default=DEFAULT_MAX_ERRORS, metavar="N", help="retain the first N errors while checking all lines; default 20")

    for command, help_text in (
        ("dupes", "find duplicate content using SHA-256; never delete files"),
        ("sizes", "summarize logical file sizes and show the largest files"),
    ):
        scanner = commands.add_parser(command, help=help_text)
        scanner.add_argument("directory", nargs="?", default=".")
        scanner.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="exclude a basename or relative path; repeatable, case-sensitive")
        scanner.add_argument("--include-ignored", action="store_true", help="include normally skipped dependency/cache directories")
        scanner.add_argument("--json", action="store_true", dest="as_json", help="emit a machine-readable JSON report")
        if command == "dupes":
            scanner.add_argument("--min-size", type=_non_negative, default=1, metavar="BYTES", help="minimum file size; default 1 skips empty files")
            scanner.add_argument("--fail-if-found", action="store_true", help="return exit code 1 when duplicate groups exist")
        else:
            scanner.add_argument("--top", type=_positive, default=10, help="maximum number of largest files to show")
    return parser


def _read_json(file: str) -> str:
    if file == "-":
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        data = stream.read(MAX_JSON_BYTES + 1)
        if isinstance(data, str):
            data = data.encode("utf-8")
    else:
        with Path(file).expanduser().open("rb") as stream:
            data = stream.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("JSON input exceeds the 16 MiB limit")
    # parse_json owns the single optional BOM; do not strip another here.
    return data.decode("utf-8")


def _human_size(size: int) -> str:
    number = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if number < 1024 or unit == "PiB":
            return f"{number:.1f} {unit}"
        number /= 1024
    raise AssertionError("unreachable")


def _path(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _print_report(command: str, report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"Root: {_path(report['root'])}")
    print(f"Files scanned: {report['files_scanned']}")
    if command == "dupes":
        print(f"Duplicate groups: {len(report['groups'])}")
        print(f"Redundant content: {_human_size(report['redundant_bytes'])} (logical estimate)")
        print(f"Files hashed: {report['files_hashed']}; hard-link aliases skipped: {report['hardlinks_skipped']}")
        for index, group in enumerate(report["groups"], start=1):
            print(f"\nGroup {index}: {_human_size(group['size_bytes'])} each; SHA-256 {group['sha256']}")
            for path in group["paths"]:
                print(f"  {_path(path)}")
    else:
        print(f"Total: {_human_size(report['total_bytes'])} (logical file sizes)")
        print("\nTop-level directories (./ = files directly under root):")
        for item in report["directories"]:
            print(f"  {_human_size(item['size_bytes']):>12}  {item['files']:>6} files  {_path(item['path'])}")
        print("\nLargest files:")
        for item in report["largest_files"]:
            print(f"  {_human_size(item['size_bytes']):>12}  {_path(item['path'])}")
    print(f"\nSkipped links: {report['symlinks_skipped']}; excluded entries: {report['excluded_entries']}")
    for error in report["errors"]:
        print(f"warning: {error}", file=sys.stderr)


def _print_jsonl_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"Lines checked: {report['lines_checked']}; valid: {report['valid_lines']}; invalid: {report['invalid_lines']}")
    for error in report["errors"]:
        print(f"line {error['line']}: {error['message']}", file=sys.stderr)
    if report["errors_omitted"]:
        print(f"Additional errors omitted: {report['errors_omitted']}", file=sys.stderr)
    if not report["complete"]:
        print(f"error: incomplete input: {report['read_error']}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # UTF-8 and LF output on Windows consoles as well as redirected streams.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace", newline="\n")
    try:
        if args.command == "json":
            text = _read_json(args.file)
            if args.check:
                parse_json(text)
            else:
                sys.stdout.write(format_json(text, indent=args.indent, sort_keys=args.sort_keys, compact=args.compact))
            return 0
        if args.command == "jsonl":
            options = {"max_line_bytes": args.max_line_bytes, "max_errors": args.max_errors}
            if args.file == "-":
                report = validate_jsonl(getattr(sys.stdin, "buffer", sys.stdin), **options)
            else:
                with Path(args.file).expanduser().open("rb") as stream:
                    report = validate_jsonl(stream, **options)
            _print_jsonl_report(report, args.as_json)
            return 2 if report["invalid_lines"] or not report["complete"] else 0
        scan = scan_directory(args.directory, exclude=tuple(args.exclude), include_ignored=args.include_ignored)
        report = duplicate_report(scan, min_size=args.min_size) if args.command == "dupes" else size_report(scan, top=args.top)
        _print_report(args.command, report, args.as_json)
        if report["errors"]:
            return 2
        if args.command == "dupes" and args.fail_if_found and report["groups"]:
            return 1
        return 0
    except (OSError, ValueError, UnicodeError, JsonError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
