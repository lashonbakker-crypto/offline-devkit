import io
import unittest

from offline_devkit.jsonl_tools import validate_jsonl


class JsonLinesTests(unittest.TestCase):
    def validate(self, data, **options):
        return validate_jsonl(io.BytesIO(data), **options)

    def test_values_unicode_and_extreme_numbers_are_valid(self):
        data = '{"猫":1E-400}\n[9007199254740993123456789]\nnull\ntrue\n"text"\n-0'.encode("utf-8")
        report = self.validate(data)
        self.assertEqual(report["lines_checked"], 6)
        self.assertEqual(report["valid_lines"], 6)
        self.assertEqual(report["invalid_lines"], 0)
        self.assertTrue(report["complete"])

    def test_crlf_and_optional_final_newline(self):
        for data in (b"{}\r\n[]\r\n", b"{}\n[]", b"{}\n[]\n"):
            with self.subTest(data=data):
                report = self.validate(data)
                self.assertEqual((report["lines_checked"], report["valid_lines"]), (2, 2))

    def test_empty_stream_contains_no_invalid_records(self):
        report = self.validate(b"")
        self.assertEqual(report["lines_checked"], 0)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["complete"])

    def test_blank_lines_are_not_silently_skipped(self):
        report = self.validate(b"{}\n\n \t\r\nnull\n")
        self.assertEqual(report["valid_lines"], 2)
        self.assertEqual([error["line"] for error in report["errors"]], [2, 3])

    def test_duplicate_keys_and_nonstandard_numbers_report_physical_lines(self):
        report = self.validate(b'{"x":1}\n{"a":1,"\\u0061":2}\nNaN\n{} {}\n')
        self.assertEqual(report["invalid_lines"], 3)
        self.assertEqual([error["line"] for error in report["errors"]], [2, 3, 4])
        self.assertIn("duplicate object key", report["errors"][0]["message"])
        self.assertIn("non-standard", report["errors"][1]["message"])

    def test_bom_and_invalid_utf8_are_errors_and_scan_continues(self):
        report = self.validate(b"\xef\xbb\xbf{}\n\xff\n{}\n")
        self.assertEqual((report["invalid_lines"], report["valid_lines"]), (2, 1))
        self.assertIn("BOM", report["errors"][0]["message"])
        self.assertEqual(report["errors"][1]["line"], 2)

    def test_byte_limit_excludes_lf_or_crlf_and_counts_unicode_bytes(self):
        for data in (b"null\n", b"null\r\n", b"null"):
            with self.subTest(data=data):
                self.assertEqual(self.validate(data, max_line_bytes=4)["valid_lines"], 1)
        report = self.validate('"猫"\n{}\n'.encode("utf-8"), max_line_bytes=4)
        self.assertEqual((report["invalid_lines"], report["valid_lines"]), (1, 1))

    def test_oversized_record_is_drained_without_unbounded_reads(self):
        class GuardedStream(io.BytesIO):
            def read(self, size=-1):
                raise AssertionError("must use bounded readline")

            def readline(self, size=-1):
                if size < 0 or size > 65536:
                    raise AssertionError("unbounded or oversized read")
                return super().readline(size)

        data = b'"' + b"x" * 200000 + b'"\n{}\n'
        report = validate_jsonl(GuardedStream(data), max_line_bytes=8)
        self.assertEqual((report["lines_checked"], report["invalid_lines"], report["valid_lines"]), (2, 1, 1))
        self.assertEqual(report["errors"][0]["line"], 1)

    def test_oversized_final_line_is_one_error(self):
        report = self.validate(b"x" * 200000, max_line_bytes=8)
        self.assertEqual((report["lines_checked"], report["invalid_lines"]), (1, 1))

    def test_error_sample_is_bounded_but_all_records_are_counted(self):
        report = self.validate(b"NaN\n" * 100 + b"{}\n", max_errors=2)
        self.assertEqual(report["lines_checked"], 101)
        self.assertEqual(report["invalid_lines"], 100)
        self.assertEqual(report["valid_lines"], 1)
        self.assertEqual(len(report["errors"]), 2)
        self.assertEqual(report["errors_omitted"], 98)
        self.assertEqual(self.validate(b"NaN\n", max_errors=0)["errors_omitted"], 1)

    def test_read_error_preserves_counts_and_marks_incomplete(self):
        class BrokenStream(io.BytesIO):
            def readline(self, size=-1):
                if self.tell():
                    raise OSError("simulated read failure")
                return super().readline(size)

        report = validate_jsonl(BrokenStream(b"{}\n[]\n"))
        self.assertEqual(report["valid_lines"], 1)
        self.assertFalse(report["complete"])
        self.assertIn("read failure", report["read_error"])

    def test_invalid_limits_are_rejected(self):
        for options in ({"max_line_bytes": 0}, {"max_errors": -1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.validate(b"{}\n", **options)

    def test_read_error_while_draining_retains_known_invalid_line(self):
        class BrokenStream(io.BytesIO):
            def readline(self, size=-1):
                if self.tell():
                    raise OSError("read failed while draining")
                return super().readline(size)

        report = validate_jsonl(BrokenStream(b"x" * 100), max_line_bytes=8)
        self.assertEqual((report["lines_checked"], report["invalid_lines"]), (1, 1))
        self.assertFalse(report["complete"])
        self.assertEqual(report["errors"][0]["line"], 1)


if __name__ == "__main__":
    unittest.main()
