import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from offline_devkit.files import (
    CHUNK_BYTES, duplicate_report, scan_directory, sha256_file, size_report,
)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, name, content=b"same"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_same_size_different_content_is_not_a_duplicate(self):
        self.write("a.txt", b"same")
        self.write("copies/b.txt", b"same")
        self.write("c.txt", b"diff")
        self.write("unique.txt", b"a different size")
        report = duplicate_report(scan_directory(self.root))
        self.assertEqual(report["files_hashed"], 3)
        self.assertEqual(len(report["groups"]), 1)
        self.assertEqual(report["groups"][0]["paths"], ["a.txt", "copies/b.txt"])
        self.assertEqual(report["redundant_bytes"], 4)
        self.assertEqual(report["groups"][0]["sha256"], hashlib.sha256(b"same").hexdigest())

    def test_hash_streams_multiple_chunks(self):
        content = b"abc\x00" * (CHUNK_BYTES // 2 + 1)
        self.write("large.bin", content)
        record = scan_directory(self.root).files[0]
        self.assertEqual(sha256_file(record), hashlib.sha256(content).hexdigest())

    def test_empty_files_are_opt_in(self):
        self.write("empty-a", b"")
        self.write("empty-b", b"")
        scan = scan_directory(self.root)
        self.assertEqual(duplicate_report(scan)["groups"], [])
        report = duplicate_report(scan, min_size=0)
        self.assertEqual(len(report["groups"]), 1)
        self.assertEqual(report["redundant_bytes"], 0)

    def test_minimum_size_filters_candidates(self):
        self.write("a", b"same")
        self.write("b", b"same")
        self.assertEqual(duplicate_report(scan_directory(self.root), min_size=5)["groups"], [])

    def test_default_exclusions_and_override(self):
        self.write("src/main.py")
        self.write(".git/config")
        self.write("a/node_modules/pkg/index.js")
        self.write(".venv/python")
        scan = scan_directory(self.root)
        self.assertEqual([file.relative_path for file in scan.files], ["src/main.py"])
        self.assertEqual(scan.excluded_entries, 3)
        self.assertEqual(len(scan_directory(self.root, include_ignored=True).files), 4)

    def test_globs_match_basename_or_relative_path(self):
        for name in ("a.log", "src/b.log", "src/main.py", "docs/notes.md", "keep.txt"):
            self.write(name)
        scan = scan_directory(self.root, exclude=("*.log", "docs/*"))
        self.assertEqual([file.relative_path for file in scan.files], ["keep.txt", "src/main.py"])

    def test_empty_directory_is_a_valid_report(self):
        scan = scan_directory(self.root)
        self.assertEqual(duplicate_report(scan)["groups"], [])
        report = size_report(scan)
        self.assertEqual(report["total_bytes"], 0)
        self.assertEqual(report["largest_files"], [])

    def test_size_buckets_include_nested_files(self):
        self.write("root.txt", b"abc")
        self.write("src/a", b"12345")
        self.write("src/deep/b", b"1234567")
        self.write("docs/c", b"x")
        report = size_report(scan_directory(self.root), top=2)
        self.assertEqual(report["total_bytes"], 16)
        self.assertEqual(report["directories"], [
            {"path": "src", "files": 2, "size_bytes": 12},
            {"path": "./", "files": 1, "size_bytes": 3},
            {"path": "docs", "files": 1, "size_bytes": 1},
        ])
        self.assertEqual([file["path"] for file in report["largest_files"]], ["src/deep/b", "src/a"])

    def test_output_order_is_deterministic(self):
        for name in ("z", "a", "b"):
            self.write(name)
        report = duplicate_report(scan_directory(self.root))
        self.assertEqual(report["groups"][0]["paths"], ["a", "b", "z"])
        self.assertEqual([file["path"] for file in size_report(scan_directory(self.root))["largest_files"]], ["a", "b", "z"])

    def symlink(self, target, link, *, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlinks unavailable: {error}")

    def test_symlinks_and_broken_symlinks_are_skipped(self):
        target = self.write("real/a")
        self.symlink(target, self.root / "file-link")
        self.symlink(self.root / "real", self.root / "directory-link", directory=True)
        self.symlink(self.root / "missing", self.root / "broken")
        scan = scan_directory(self.root)
        self.assertEqual([file.relative_path for file in scan.files], ["real/a"])
        self.assertEqual(scan.symlinks_skipped, 3)

    def test_symlink_root_is_rejected(self):
        directory = self.root / "real"
        directory.mkdir()
        link = self.root / "link"
        self.symlink(directory, link, directory=True)
        with self.assertRaisesRegex(ValueError, "real directory"):
            scan_directory(link)

    def test_file_root_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "real directory"):
            scan_directory(self.write("file"))

    def test_hardlinks_do_not_inflate_duplicate_estimate(self):
        target = self.write("a")
        try:
            os.link(target, self.root / "alias")
        except OSError as error:
            self.skipTest(f"hardlinks unavailable: {error}")
        self.write("copy")
        report = duplicate_report(scan_directory(self.root))
        self.assertEqual(report["hardlinks_skipped"], 1)
        self.assertEqual(report["redundant_bytes"], 4)
        self.assertEqual(report["groups"][0]["paths"], ["a", "copy"])

    def test_file_changed_after_scan_is_reported(self):
        target = self.write("a")
        self.write("b")
        scan = scan_directory(self.root)
        target.write_bytes(b"changed content")
        report = duplicate_report(scan)
        self.assertEqual(report["groups"], [])
        self.assertEqual(len(report["errors"]), 1)
        self.assertIn("file changed", report["errors"][0])

    def test_removed_file_is_reported(self):
        target = self.write("a")
        self.write("b")
        scan = scan_directory(self.root)
        target.unlink()
        report = duplicate_report(scan)
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(report["groups"], [])

    def test_unreadable_directory_has_an_explicit_error(self):
        with patch("offline_devkit.files.os.scandir", side_effect=PermissionError(13, "Permission denied")):
            scan = scan_directory(self.root)
        self.assertEqual(scan.files, [])
        self.assertEqual(len(scan.errors), 1)
        self.assertIn("Permission denied", scan.errors[0])

    def test_special_files_are_skipped(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO creation unavailable")
        os.mkfifo(self.root / "pipe")
        self.assertEqual(scan_directory(self.root).files, [])


if __name__ == "__main__":
    unittest.main()
