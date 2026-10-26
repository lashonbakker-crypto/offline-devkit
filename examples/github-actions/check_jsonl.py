"""Check one JSONL file with a checksum-pinned Offline DevKit v0.4.0 archive.

Copy to .github/scripts/check_jsonl.py alongside the workflow recipe. The
optional --archive path uses an existing copy without network access; the same
fixed checksum is required. Only temporary tool files are written.
"""

import argparse
import hashlib
from http.client import HTTPException
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import urlopen

RELEASE_URL = "https://github.com/lashonbakker-crypto/offline-devkit/releases/download/v0.4.0/offline-devkit.pyz"
RELEASE_SHA256 = "349b3fdda2c55f37e2c422935ef63718f2950f65076fe0f45309ad4f0e44fc64"
MAX_ARCHIVE_BYTES = 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 30


def archive_bytes(existing: Path | None) -> bytes:
    """Read bounded bytes, then check the independently pinned release digest."""
    if existing is None:
        try:
            with urlopen(RELEASE_URL, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
                data = response.read(MAX_ARCHIVE_BYTES + 1)
        except HTTPException as error:
            raise OSError(f"tool download failed: {error}") from error
    else:
        if not existing.is_file():
            raise ValueError("--archive must be an existing regular file")
        with existing.open("rb") as stream:
            data = stream.read(MAX_ARCHIVE_BYTES + 1)
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("archive exceeds the 1 MiB size limit")
    if hashlib.sha256(data).hexdigest() != RELEASE_SHA256:
        raise ValueError("archive SHA-256 mismatch; refusing to execute")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="one explicit existing JSONL file")
    parser.add_argument("--gzip", action="store_true", help="read gzip-compressed input")
    parser.add_argument("--archive", type=Path, help="existing v0.4.0 pyz; the fixed SHA-256 still applies")
    args = parser.parse_args()
    try:
        source = args.file.expanduser().resolve(strict=True)
        if not source.is_file():
            raise ValueError("input must be an existing regular file")
        data = archive_bytes(args.archive.expanduser() if args.archive is not None else None)
        with tempfile.TemporaryDirectory(prefix="offline-devkit-ci-") as temporary:
            work = Path(temporary)
            archive = work / "offline-devkit.pyz"
            archive.write_bytes(data)
            options = ["--gzip"] if args.gzip else []
            # Execute the verified copy outside the checkout with isolated imports.
            # Inherit stdout/stderr so the validator's JSON and status pass through.
            result = subprocess.run(
                [sys.executable, "-I", str(archive), "jsonl", str(source), *options, "--json"],
                stdin=subprocess.DEVNULL, cwd=work, check=False,
            )
            return result.returncode
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
