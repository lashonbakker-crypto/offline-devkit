import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from offline_devkit.cli import main
from offline_devkit.files import Scan

REPO_ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def invoke(self, *args, input_text=""):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors), patch("sys.stdin", io.StringIO(input_text)):
            status = main(args)
        return status, output.getvalue(), errors.getvalue()

    def test_stdin_formats_unicode_and_preserves_numbers(self):
        status, output, errors = self.invoke("json", "--compact", input_text='{"猫":0.123456789012345678901}')
        self.assertEqual(status, 0)
        self.assertEqual(errors, "")
        self.assertEqual(output, '{"猫":0.123456789012345678901}\n')

    def test_check_emits_no_output(self):
        status, output, errors = self.invoke("json", "--check", input_text="[1,2]")
        self.assertEqual((status, output, errors), (0, "", ""))

    def test_jsonl_stdin_reports_line_number_and_exit_two(self):
        status, output, errors = self.invoke("jsonl", "--json", input_text='{}\n{"x":1,"x":2}\nnull\n')
        self.assertEqual((status, errors), (2, ""))
        report = json.loads(output)
        self.assertEqual(report["valid_lines"], 2)
        self.assertEqual(report["errors"][0]["line"], 2)

    def test_jsonl_file_success_and_bounded_error_sample(self):
        path = self.root / "records.jsonl"
        path.write_bytes(b"{}\r\nnull")
        status, output, errors = self.invoke("jsonl", str(path))
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("valid: 2; invalid: 0", output)
        path.write_bytes(b"NaN\nNaN\n{}\n")
        status, output, errors = self.invoke("jsonl", str(path), "--max-errors", "0", "--json")
        self.assertEqual((status, errors), (2, ""))
        self.assertEqual(json.loads(output)["errors_omitted"], 2)

    def test_jsonl_read_failure_is_not_success(self):
        report = {"lines_checked": 1, "valid_lines": 1, "invalid_lines": 0, "errors": [], "errors_omitted": 0, "complete": False, "read_error": "disk read failure"}
        with patch("offline_devkit.cli.validate_jsonl", return_value=report):
            status, output, errors = self.invoke("jsonl", "--json")
        self.assertEqual((status, errors), (2, ""))
        self.assertFalse(json.loads(output)["complete"])

    def test_jsonl_binary_pipe_in_a_real_process(self):
        result = subprocess.run(
            [sys.executable, "-m", "offline_devkit", "jsonl", "--json"],
            input='{"猫":1E-400}\nNaN\n'.encode("utf-8"),
            capture_output=True, cwd=REPO_ROOT, check=False,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertNotIn(b"\r\n", result.stdout)
        self.assertEqual(json.loads(result.stdout)["valid_lines"], 1)

    def test_invalid_json_has_exit_two_and_no_stdout(self):
        status, output, errors = self.invoke("json", input_text='{"x":NaN}')
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("non-standard", errors)

    def test_invalid_utf8_has_controlled_error(self):
        path = self.root / "bad.json"
        path.write_bytes(b"\xff")
        status, output, errors = self.invoke("json", str(path))
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("error:", errors)

    def test_bom_file_is_accepted(self):
        path = self.root / "bom.json"
        path.write_bytes(b"\xef\xbb\xbf{\"x\":1}")
        status, _, errors = self.invoke("json", str(path), "--check")
        self.assertEqual((status, errors), (0, ""))

    def test_binary_json_accepts_one_bom_but_rejects_repeated_boms(self):
        path = self.root / "bom.json"
        for prefixes in (0, 1, 2, 3):
            data = b"\xef\xbb\xbf" * prefixes + b'{"number":1E-400}'
            path.write_bytes(data)
            for source in (str(path), "-"):
                for mode in ("--check", "--compact"):
                    with self.subTest(prefixes=prefixes, source=source, mode=mode):
                        result = subprocess.run(
                            [sys.executable, "-m", "offline_devkit", "json", source, mode],
                            input=data if source == "-" else None,
                            capture_output=True, cwd=REPO_ROOT, check=False,
                        )
                        if prefixes <= 1:
                            self.assertEqual(result.returncode, 0, result.stderr)
                            self.assertEqual(result.stderr, b"")
                            expected = b"" if mode == "--check" else b'{"number":1E-400}\n'
                            self.assertEqual(result.stdout, expected)
                        else:
                            self.assertEqual(result.returncode, 2, result.stderr)
                            self.assertEqual(result.stdout, b"")
                            self.assertIn(b"BOM", result.stderr)
            self.assertEqual(path.read_bytes(), data)

    def test_input_limit_for_file_and_stdin(self):
        path = self.root / "large.json"
        path.write_text("[123456789]", encoding="utf-8")
        with patch("offline_devkit.cli.MAX_JSON_BYTES", 8):
            for file in (str(path), "-"):
                with self.subTest(file=file):
                    status, output, errors = self.invoke("json", file, input_text="[123456789]")
                    self.assertEqual(status, 2)
                    self.assertEqual(output, "")
                    self.assertIn("limit", errors)

    def test_duplicate_report_exit_codes(self):
        for name in ("a", "b"):
            (self.root / name).write_bytes(b"same")
        for fail in (False, True):
            args = ["dupes", str(self.root), "--json"]
            if fail:
                args.append("--fail-if-found")
            status, output, errors = self.invoke(*args)
            self.assertEqual(status, 1 if fail else 0)
            self.assertEqual(errors, "")
            self.assertEqual(json.loads(output)["groups"][0]["paths"], ["a", "b"])
        self.assertEqual((self.root / "a").read_bytes(), b"same")
        self.assertEqual((self.root / "b").read_bytes(), b"same")

    def test_duplicate_byte_verification_is_reported(self):
        for name in ("a", "b"):
            (self.root / name).write_bytes(b"same")
        status, output, errors = self.invoke(
            "dupes", str(self.root), "--json", "--verify-bytes",
        )
        report = json.loads(output)
        self.assertEqual((status, errors), (0, ""))
        self.assertTrue(report["verify_bytes"])
        self.assertEqual(report["byte_comparisons"], 1)
        self.assertEqual(report["groups"][0]["verified_by"], "bytes")

    def test_missing_directory_has_exit_two(self):
        status, output, errors = self.invoke("sizes", str(self.root / "missing"))
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("error:", errors)

    def test_unresolved_home_path_has_exit_two_before_filesystem_access(self):
        source = "~unavailable-user/data"
        for command in ("json", "jsonl", "dupes", "sizes"):
            with self.subTest(command=command):
                options = ["--check"] if command == "json" else ["--json"]
                with (
                    patch.object(Path, "expanduser", side_effect=RuntimeError("home lookup failed")),
                    patch.object(Path, "open") as open_file,
                    patch.object(Path, "lstat") as lstat,
                    patch("offline_devkit.files.os.scandir") as scandir,
                ):
                    status, output, errors = self.invoke(command, source, *options)
                self.assertEqual((status, output), (2, ""))
                self.assertIn("cannot expand user path", errors)
                self.assertIn(repr(str(Path(source))), errors)
                self.assertIn("home lookup failed", errors)
                self.assertNotIn("Traceback", errors)
                open_file.assert_not_called()
                lstat.assert_not_called()
                scandir.assert_not_called()

    def test_partial_scan_is_not_reported_as_success(self):
        scan = Scan(root=self.root, errors=["permission denied"])
        with patch("offline_devkit.cli.scan_directory", return_value=scan):
            status, output, _ = self.invoke("sizes", str(self.root), "--json")
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output)["errors"], ["permission denied"])

    def test_directory_replacement_returns_two_for_both_reports(self):
        for command in ("sizes", "dupes"):
            with self.subTest(command=command):
                root = self.root / command
                directory = root / "a-pending"
                directory.mkdir(parents=True)
                (directory / "original.txt").write_bytes(b"same")
                marker = root / "z-marker.txt"
                marker.write_bytes(b"same")
                original_lstat = Path.lstat
                changed = False

                def lstat(path, *args, **kwargs):
                    nonlocal changed
                    info = original_lstat(path, *args, **kwargs)
                    if path == marker and not changed:
                        changed = True
                        directory.rename(root / "saved")
                        directory.mkdir()
                        (directory / "original.txt").write_bytes(b"same")
                    return info

                with patch.object(Path, "lstat", lstat):
                    args = [command, str(root), "--json"]
                    if command == "dupes":
                        args.append("--fail-if-found")
                    status, output, errors = self.invoke(*args)
                self.assertEqual(status, 2)
                self.assertEqual(errors, "")
                report = json.loads(output)
                self.assertEqual(report["files_scanned"], 1)
                self.assertEqual(len(report["errors"]), 1)
                self.assertIn("directory changed", report["errors"][0])

    def test_sizes_json_and_top(self):
        (self.root / "a").write_bytes(b"abc")
        (self.root / "b").write_bytes(b"12345")
        status, output, errors = self.invoke("sizes", str(self.root), "--json", "--top", "1")
        self.assertEqual((status, errors), (0, ""))
        report = json.loads(output)
        self.assertEqual(report["total_bytes"], 8)
        self.assertEqual(report["largest_files"], [{"path": "b", "size_bytes": 5}])

    def test_command_line_binary_stdin_in_a_real_process(self):
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, "-m", "offline_devkit", "json", "--compact"],
            input='{"中文":1E-400}'.encode("utf-8"),
            capture_output=True, cwd=REPO_ROOT, env=environment, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode("utf-8"), '{"中文":1E-400}\n')


if __name__ == "__main__":
    unittest.main()
