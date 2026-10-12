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

    def test_missing_directory_has_exit_two(self):
        status, output, errors = self.invoke("sizes", str(self.root / "missing"))
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("error:", errors)

    def test_partial_scan_is_not_reported_as_success(self):
        scan = Scan(root=self.root, errors=["permission denied"])
        with patch("offline_devkit.cli.scan_directory", return_value=scan):
            status, output, _ = self.invoke("sizes", str(self.root), "--json")
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output)["errors"], ["permission denied"])

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
