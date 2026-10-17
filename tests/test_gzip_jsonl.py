import gzip
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from offline_devkit.jsonl_tools import validate_gzip_jsonl

ROOT = Path(__file__).resolve().parents[1]


class GzipJsonLinesTests(unittest.TestCase):
    def test_unicode_numbers_crlf_and_missing_final_newline(self):
        data = gzip.compress('{"猫":1E-400}\r\n[9007199254740993123456789]\r\nnull'.encode("utf-8"))
        stream = io.BytesIO(data)
        report = validate_gzip_jsonl(stream)
        self.assertEqual((report["lines_checked"], report["valid_lines"]), (3, 3))
        self.assertTrue(report["complete"])
        self.assertIsNone(report["read_error"])
        self.assertFalse(stream.closed)
        self.assertEqual(stream.getvalue(), data)

    def test_members_are_one_continuous_jsonl_stream(self):
        data = gzip.compress(b'{"x":') + gzip.compress(b'1}\nNaN\n') + gzip.compress(b'null')
        report = validate_gzip_jsonl(io.BytesIO(data))
        self.assertEqual((report["lines_checked"], report["valid_lines"], report["invalid_lines"]), (3, 2, 1))
        self.assertEqual(report["errors"][0]["line"], 2)
        self.assertTrue(report["complete"])

    def test_line_limit_applies_after_decompression_and_scan_continues(self):
        data = gzip.compress(b'"' + b"x" * 200000 + b'"\n{}\nNaN\nNaN\n')
        report = validate_gzip_jsonl(io.BytesIO(data), max_line_bytes=8, max_errors=1)
        self.assertEqual((report["lines_checked"], report["valid_lines"], report["invalid_lines"]), (4, 1, 3))
        self.assertEqual(report["errors"][0], {"line": 1, "message": "line exceeds 8 bytes"})
        self.assertEqual(report["errors_omitted"], 2)
        self.assertTrue(report["complete"])

    def test_corrupt_and_truncated_streams_are_incomplete(self):
        good = gzip.compress(b"{}\n[]\n", mtime=0)
        crc = bytearray(good)
        crc[-8] ^= 1
        size = bytearray(good)
        size[-4] ^= 1
        deflate = bytearray(good)
        deflate[10] = 7  # Reserved DEFLATE block type.
        cases = {
            "wrong format": b"not gzip",
            "header": good[:1],
            "body": good[:12],
            "trailer": good[:-1],
            "CRC": bytes(crc),
            "size": bytes(size),
            "deflate": bytes(deflate),
            "trailing garbage": good + b"garbage",
        }
        for case, data in cases.items():
            with self.subTest(case=case):
                report = validate_gzip_jsonl(io.BytesIO(data))
                self.assertFalse(report["complete"])
                self.assertTrue(report["read_error"])

    def test_error_in_later_member_retains_already_checked_records(self):
        data = gzip.compress(b"{}\nnull\n") + gzip.compress(b"[]\n")[:-8]
        report = validate_gzip_jsonl(io.BytesIO(data))
        self.assertFalse(report["complete"])
        self.assertGreaterEqual(report["valid_lines"], 2)
        self.assertEqual(report["lines_checked"], report["valid_lines"])

    def test_empty_and_empty_member_follow_standard_gzip_reader(self):
        for data in (b"", gzip.compress(b"")):
            with self.subTest(data=data):
                report = validate_gzip_jsonl(io.BytesIO(data))
                self.assertTrue(report["complete"])
                self.assertEqual(report["lines_checked"], 0)

    def test_real_cli_reads_gzip_files_and_binary_stdin_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "records.bin"
            valid = gzip.compress('{"猫":1E-400}\nnull'.encode("utf-8"))
            invalid = gzip.compress(b"{}\nNaN\n")
            broken = valid[:-4]
            for data, code in ((valid, 0), (invalid, 2), (broken, 2), (b"not gzip", 2)):
                path.write_bytes(data)
                for source in (str(path), "-"):
                    with self.subTest(source=source, code=code):
                        result = subprocess.run(
                            [sys.executable, "-m", "offline_devkit", "jsonl", source, "--gzip", "--json"],
                            input=data if source == "-" else None,
                            capture_output=True, cwd=ROOT, timeout=10,
                        )
                        self.assertEqual(result.returncode, code, result.stderr)
                        self.assertEqual(result.stderr, b"")
                        report = json.loads(result.stdout)
                        self.assertEqual(report["complete"], data in (valid, invalid))
                        if data == invalid:
                            self.assertEqual(report["errors"][0]["line"], 2)
                        self.assertEqual(path.read_bytes(), data)

    def test_suffix_does_not_enable_decompression_implicitly(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "plain.jsonl.gz"
            path.write_bytes(b"{}\n")
            result = subprocess.run(
                [sys.executable, "-m", "offline_devkit", "jsonl", str(path), "--json"],
                capture_output=True, cwd=ROOT, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["valid_lines"], 1)


if __name__ == "__main__":
    unittest.main()
