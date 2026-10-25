"""Measure size-report elapsed time and Python allocations on synthetic metadata.

No directory is scanned and no dataset files are created. This measures report
construction after inventory, not filesystem I/O, process RSS, or CLI startup.
"""

import argparse
import gc
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", nargs="+", type=positive, default=[1000, 10000, 100000])
    parser.add_argument("--top", type=positive, default=10)
    parser.add_argument("--repeats", type=positive, default=5)
    parser.add_argument("--source-root", type=Path, default=ROOT, help="source checkout to measure (default: this repository)")
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    if not (source_root / "offline_devkit" / "files.py").is_file():
        parser.error("--source-root must contain offline_devkit/files.py")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source_root))
    from offline_devkit.files import FileRecord, Scan, size_report

    results = []
    for count in args.counts:
        root = Path("synthetic-size-benchmark")
        records = []
        for index in range(count):
            relative = f"group-{index % 64:02d}/file-{index:09d}.bin"
            # Repeated sizes deliberately exercise path ordering at ties.
            size = (index * 7919) % 10007
            records.append(FileRecord(root / relative, relative, size, 0, 1, index + 1))
        scan = Scan(root=root, files=records)
        expected = [
            {"path": item.relative_path, "size_bytes": item.size}
            for item in sorted(records, key=lambda item: (-item.size, item.relative_path))[:args.top]
        ]
        total_bytes = sum(item.size for item in records)

        def checked_report():
            report = size_report(scan, top=args.top)
            if report["largest_files"] != expected or report["total_bytes"] != total_bytes:
                raise RuntimeError("size report disagrees with full-sort reference")
            if report["files_scanned"] != count or report["errors"]:
                raise RuntimeError("unexpected scan metadata")
            return report

        # Warm once. Keep checking outside each timed/traced interval so the
        # oracle's sorting and JSON serialization do not distort measurements.
        checked_report()
        samples = []
        for _ in range(args.repeats):
            gc.collect()
            started = time.perf_counter()
            report = size_report(scan, top=args.top)
            samples.append(time.perf_counter() - started)
            if report != checked_report():
                raise RuntimeError("report changed between repeated runs")
        gc.collect()
        tracemalloc.start()
        try:
            report = size_report(scan, top=args.top)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        if report != checked_report():
            raise RuntimeError("traced report differs from the verified report")
        # A digest over the complete report permits comparisons across source
        # checkouts, including directory totals, paths, and metadata fields.
        encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        results.append({
            "files": count,
            "median_seconds": statistics.median(samples),
            "samples_seconds": samples,
            "peak_traced_bytes": peak,
            "report_sha256": hashlib.sha256(encoded).hexdigest(),
        })
    print(json.dumps({
        "python": platform.python_version(),
        "system": platform.system(),
        "scope": "size_report_only; synthetic metadata already allocated; tracemalloc is not RSS",
        "top": args.top,
        "repeats": args.repeats,
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
