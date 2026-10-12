"""Read-only directory inventory and SHA-256 duplicate discovery."""

import fnmatch
import hashlib
import os
import stat
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_EXCLUDED_DIRS = frozenset(
    {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
)
CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class FileRecord:
    path: Path
    relative_path: str
    size: int
    mtime_ns: int
    device: int
    inode: int


@dataclass
class Scan:
    root: Path
    files: list[FileRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    symlinks_skipped: int = 0
    excluded_entries: int = 0


def _linked(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & reparse_point)


def _excluded(relative: str, name: str, patterns: tuple[str, ...]) -> bool:
    return any(
        fnmatch.fnmatchcase(relative, pattern) or fnmatch.fnmatchcase(name, pattern)
        for pattern in patterns
    )


def scan_directory(
    root: Path | str,
    *,
    exclude: tuple[str, ...] = (),
    include_ignored: bool = False,
) -> Scan:
    """Inspect regular files. Do not traverse symlinks or Windows reparse points."""
    root = Path(root).expanduser().absolute()
    info = root.lstat()
    if _linked(info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError("root must be a real directory, not a symlink or file")
    scan = Scan(root=root)
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError as error:
            relative = directory.relative_to(root).as_posix()
            scan.errors.append(f"{relative!r}: {error.strerror or str(error)}")
            continue
        for entry in entries:
            path = directory / entry.name
            relative = path.relative_to(root).as_posix()
            try:
                info = entry.stat(follow_symlinks=False)
                if _linked(info):
                    scan.symlinks_skipped += 1
                    continue
                is_directory = stat.S_ISDIR(info.st_mode)
                if _excluded(relative, entry.name, exclude) or (
                    is_directory
                    and not include_ignored
                    and entry.name in DEFAULT_EXCLUDED_DIRS
                ):
                    scan.excluded_entries += 1
                    continue
                if is_directory:
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    scan.files.append(
                        FileRecord(
                            path, relative, info.st_size, info.st_mtime_ns,
                            info.st_dev, info.st_ino,
                        )
                    )
            except OSError as error:
                scan.errors.append(f"{relative!r}: {error.strerror or str(error)}")
    scan.files.sort(key=lambda record: record.relative_path)
    scan.errors.sort()
    return scan


def _signature(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def sha256_file(record: FileRecord) -> str:
    """Hash in bounded chunks; report files changed since the directory scan."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(record.path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        expected = (record.device, record.inode, record.size, record.mtime_ns)
        if not stat.S_ISREG(before.st_mode) or _signature(before) != expected:
            raise OSError("file changed since scan; rerun when files are stable")
        digest = hashlib.sha256()
        bytes_read = 0
        while True:
            chunk = stream.read(CHUNK_BYTES)
            if not chunk:
                break
            bytes_read += len(chunk)
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        current = record.path.lstat()
        if (
            _linked(current)
            or _signature(after) != expected
            or _signature(current) != expected
            or bytes_read != record.size
        ):
            raise OSError("file changed while hashing; rerun when files are stable")
    return digest.hexdigest()


def _metadata(scan: Scan) -> dict[str, Any]:
    return {
        "root": str(scan.root),
        "files_scanned": len(scan.files),
        "symlinks_skipped": scan.symlinks_skipped,
        "excluded_entries": scan.excluded_entries,
        "errors": list(scan.errors),
    }


def duplicate_report(scan: Scan, *, min_size: int = 1) -> dict[str, Any]:
    """Compare size, then SHA-256. Hard-link aliases are counted only once."""
    if min_size < 0:
        raise ValueError("min_size must be non-negative")
    by_size: dict[int, list[FileRecord]] = defaultdict(list)
    seen = set()
    hardlinks_skipped = 0
    for record in scan.files:
        identity = (record.device, record.inode)
        if record.inode and identity in seen:
            hardlinks_skipped += 1
            continue
        if record.inode:
            seen.add(identity)
        if record.size >= min_size:
            by_size[record.size].append(record)
    report = _metadata(scan)
    groups = []
    files_hashed = 0
    for size, records in sorted(by_size.items()):
        if len(records) < 2:
            continue
        by_hash: dict[str, list[str]] = defaultdict(list)
        for record in records:
            try:
                digest = sha256_file(record)
                files_hashed += 1
                by_hash[digest].append(record.relative_path)
            except OSError as error:
                report["errors"].append(
                    f"{record.relative_path!r}: {error.strerror or str(error)}"
                )
        for digest, paths in sorted(by_hash.items()):
            if len(paths) > 1:
                groups.append({
                    "sha256": digest,
                    "size_bytes": size,
                    "paths": sorted(paths),
                    "redundant_bytes": size * (len(paths) - 1),
                })
    groups.sort(key=lambda group: (-group["redundant_bytes"], group["paths"][0]))
    report.update(
        min_size_bytes=min_size,
        files_hashed=files_hashed,
        hardlinks_skipped=hardlinks_skipped,
        groups=groups,
        redundant_bytes=sum(group["redundant_bytes"] for group in groups),
    )
    report["errors"].sort()
    return report


def size_report(scan: Scan, *, top: int = 10) -> dict[str, Any]:
    """Report logical file sizes, not filesystem allocation or freeable space."""
    if top < 1:
        raise ValueError("top must be positive")
    buckets: dict[str, dict[str, Any]] = {}
    for record in scan.files:
        name = record.relative_path.split("/", 1)[0] if "/" in record.relative_path else "./"
        bucket = buckets.setdefault(name, {"path": name, "files": 0, "size_bytes": 0})
        bucket["files"] += 1
        bucket["size_bytes"] += record.size
    report = _metadata(scan)
    report.update(
        total_bytes=sum(record.size for record in scan.files),
        largest_files=[
            {"path": record.relative_path, "size_bytes": record.size}
            for record in sorted(scan.files, key=lambda item: (-item.size, item.relative_path))[:top]
        ],
        directories=sorted(buckets.values(), key=lambda item: (-item["size_bytes"], item["path"])),
    )
    return report
