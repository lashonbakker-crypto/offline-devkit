import hashlib
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from offline_devkit.files import (
    CHUNK_BYTES, duplicate_report, files_equal, scan_directory, sha256_file,
    size_report,
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

    def test_byte_comparison_streams_multiple_chunks(self):
        content = b"abc\x00" * (CHUNK_BYTES // 2 + 1)
        self.write("a.bin", content)
        self.write("b.bin", content)
        left, right = scan_directory(self.root).files
        self.assertTrue(files_equal(left, right))
        self.write("b.bin", content[:-1] + b"x")
        right = scan_directory(self.root).files[1]
        self.assertFalse(files_equal(left, right))

    def test_optional_byte_verification_splits_a_simulated_hash_collision(self):
        self.write("a", b"same")
        self.write("b", b"same")
        self.write("collision", b"diff")
        scan = scan_directory(self.root)
        with patch("offline_devkit.files.sha256_file", return_value="0" * 64):
            hashed = duplicate_report(scan)
            verified = duplicate_report(scan, verify_bytes=True)
        self.assertEqual(hashed["groups"][0]["paths"], ["a", "b", "collision"])
        self.assertEqual(verified["groups"][0]["paths"], ["a", "b"])
        self.assertEqual(verified["groups"][0]["verified_by"], "bytes")
        self.assertEqual(verified["byte_comparisons"], 2)

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

    def test_largest_file_cutoff_preserves_ties_and_full_totals(self):
        for name, size in (("z-largest", 9), ("a", 4), ("b", 4), ("nested/c", 4), ("empty", 0)):
            self.write(name, b"x" * size)
        scan = scan_directory(self.root)
        # Reporting must not rely on inventory order when a tie crosses top N.
        scan.files.reverse()
        expected = [
            {"path": "z-largest", "size_bytes": 9},
            {"path": "a", "size_bytes": 4},
            {"path": "b", "size_bytes": 4},
            {"path": "nested/c", "size_bytes": 4},
            {"path": "empty", "size_bytes": 0},
        ]
        for top in (1, 3, 5, 99):
            with self.subTest(top=top):
                report = size_report(scan, top=top)
                self.assertEqual(report["largest_files"], expected[:top])
                self.assertEqual(report["total_bytes"], 21)
                self.assertEqual(report["files_scanned"], 5)
                self.assertEqual(sum(item["size_bytes"] for item in report["directories"]), 21)

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

    @contextmanager
    def replace_after_marker(self, marker, replace):
        """Change a queued directory after its parent has recorded it."""
        original_lstat = Path.lstat
        changed = False

        def lstat(path, *args, **kwargs):
            nonlocal changed
            info = original_lstat(path, *args, **kwargs)
            if path == marker and not changed:
                changed = True
                replace()
            return info

        with patch.object(Path, "lstat", lstat):
            yield

    def test_queued_directory_replacement_is_reported(self):
        self.write("a-pending/original.txt")
        marker = self.write("z-marker.txt")
        directory = self.root / "a-pending"

        def replace():
            directory.rename(self.root / "saved")
            directory.mkdir()
            (directory / "replacement.txt").write_bytes(b"replacement")

        with self.replace_after_marker(marker, replace):
            scan = scan_directory(self.root)
        self.assertEqual([file.relative_path for file in scan.files], ["z-marker.txt"])
        self.assertEqual(len(scan.errors), 1)
        self.assertIn("directory changed", scan.errors[0])

    def test_queued_directory_replaced_by_symlink_is_not_traversed(self):
        self.write("a-pending/original.txt")
        marker = self.write("z-marker.txt")
        directory = self.root / "a-pending"
        with tempfile.TemporaryDirectory() as temporary:
            outside = Path(temporary)
            (outside / "outside.txt").write_bytes(b"outside scan root")
            # Probe support before injecting the concurrent replacement.
            probe = self.root / "probe-link"
            self.symlink(outside, probe, directory=True)
            probe.unlink()

            def replace():
                directory.rename(self.root / "saved")
                directory.symlink_to(outside, target_is_directory=True)

            with self.replace_after_marker(marker, replace):
                with patch("offline_devkit.files.os.scandir", wraps=os.scandir) as scandir:
                    scan = scan_directory(self.root)
            self.assertEqual(scandir.call_count, 1)
        self.assertEqual([file.relative_path for file in scan.files], ["z-marker.txt"])
        self.assertEqual(len(scan.errors), 1)
        self.assertIn("directory changed", scan.errors[0])

    def test_directory_replaced_after_listing_is_reported(self):
        self.write("a-pending/original.txt")
        directory = self.root / "a-pending"
        original_scandir = os.scandir

        @contextmanager
        def scandir(path):
            with original_scandir(path) as iterator:
                yield iterator
            if path == directory:
                directory.rename(self.root / "saved")
                directory.mkdir()
                (directory / "original.txt").write_bytes(b"replacement")

        with patch("offline_devkit.files.os.scandir", scandir):
            scan = scan_directory(self.root)
        self.assertEqual(scan.files, [])
        self.assertEqual(len(scan.errors), 1)
        self.assertIn("directory changed", scan.errors[0])

    def test_special_files_are_skipped(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO creation unavailable")
        os.mkfifo(self.root / "pipe")
        self.assertEqual(scan_directory(self.root).files, [])


if __name__ == "__main__":
    unittest.main()
