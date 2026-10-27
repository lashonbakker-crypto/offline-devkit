"""Validate plain or gzip JSON Lines, retaining only a bounded error sample."""

import gzip
import sys
import zlib
from typing import Any, BinaryIO, TextIO

from .json_tools import JsonError, parse_json

DEFAULT_MAX_LINE_BYTES = 1024 * 1024
DEFAULT_MAX_ERRORS = 20
# readline's size must also fit the CRLF and oversized-line lookahead.
MAX_LINE_BYTES = sys.maxsize - 3


def validate_jsonl(
    stream: BinaryIO | TextIO,
    *,
    max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
    max_errors: int = DEFAULT_MAX_ERRORS,
) -> dict[str, Any]:
    """Check all physical lines without loading the whole input into memory.

    Blank lines and BOMs are errors. A final newline is optional. A read error
    preserves the partial counts and marks the report incomplete.
    """
    if not 1 <= max_line_bytes <= MAX_LINE_BYTES:
        raise ValueError(f"max_line_bytes must be between 1 and {MAX_LINE_BYTES}")
    if max_errors < 0:
        raise ValueError("max_errors must be non-negative")
    report: dict[str, Any] = {
        "lines_checked": 0,
        "valid_lines": 0,
        "invalid_lines": 0,
        "errors": [],
        "errors_omitted": 0,
        "complete": True,
        "read_error": None,
    }

    def read_chunk(limit: int) -> bytes:
        chunk = stream.readline(limit)
        # Text streams support embedded callers without a .buffer attribute.
        return chunk.encode("utf-8") if isinstance(chunk, str) else chunk

    try:
        while True:
            # Allow a complete CRLF plus one byte to detect an oversized line.
            chunk = read_chunk(max_line_bytes + 3)
            if not chunk:
                break
            report["lines_checked"] += 1
            line_number = report["lines_checked"]
            payload = chunk
            if payload.endswith(b"\n"):
                payload = payload[:-1]
                if payload.endswith(b"\r"):
                    payload = payload[:-1]

            message = None
            oversized = len(payload) > max_line_bytes
            if oversized:
                message = f"line exceeds {max_line_bytes} bytes"
            else:
                try:
                    text = payload.decode("utf-8")
                    if text.startswith("\ufeff"):
                        raise JsonError("UTF-8 BOM is not allowed in JSON Lines")
                    if not text.strip():
                        raise JsonError("blank lines are not valid JSON Lines records")
                    parse_json(text)
                except (UnicodeError, JsonError) as error:
                    message = str(error).removeprefix("line 1, ")

            if message is None:
                report["valid_lines"] += 1
            else:
                report["invalid_lines"] += 1
                if len(report["errors"]) < max_errors:
                    report["errors"].append({"line": line_number, "message": message})
                else:
                    report["errors_omitted"] += 1
            # Count the already-known error even if draining later fails.
            # Consume only this physical line in bounded pieces, then resume.
            while oversized and chunk and not chunk.endswith(b"\n"):
                chunk = read_chunk(64 * 1024)
    except (OSError, EOFError, zlib.error, UnicodeError) as error:
        report["complete"] = False
        report["read_error"] = str(error)
    return report


def validate_gzip_jsonl(stream: BinaryIO, **options) -> dict[str, Any]:
    """Check decompressed records, including gzip trailers and all members.

    Closing this wrapper does not close the caller's compressed stream.
    Limits apply to decompressed records, not compressed bytes. Returned
    counts cover records delivered before a read/decompression error only.
    """
    with gzip.GzipFile(fileobj=stream, mode="rb") as decompressed:
        return validate_jsonl(decompressed, **options)
