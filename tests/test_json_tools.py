import json
import unittest

from offline_devkit.json_tools import JsonError, format_json, parse_json


class JsonTests(unittest.TestCase):
    def test_numbers_keep_their_exact_tokens(self):
        tokens = [
            "9007199254740993123456789", "0.12345678901234567890123456789",
            "1e+10000", "1E-400", "-0", "-0.000", "2.0000", "9" * 5000,
        ]
        source = "[" + ",".join(tokens) + "]"
        self.assertEqual(format_json(source, compact=True), source + "\n")

    def test_pretty_output_is_valid_and_readable(self):
        source = '{"消息":"你好 🐱","list":[true,null,{"x":"a\\nb"}]}'
        output = format_json(source)
        self.assertIn("你好 🐱", output)
        self.assertEqual(json.loads(output), json.loads(source))
        self.assertTrue(output.endswith("\n"))

    def test_sort_keys_applies_to_nested_objects(self):
        self.assertEqual(
            format_json('{"z":{"b":2,"a":1},"a":0}', compact=True, sort_keys=True),
            '{"a":0,"z":{"a":1,"b":2}}\n',
        )

    def test_default_preserves_key_order(self):
        self.assertEqual(format_json('{"b":1,"a":2}', compact=True), '{"b":1,"a":2}\n')

    def test_empty_containers_and_scalar_inputs(self):
        for source in ("{}", "[]", "true", "false", "null", '"hi"'):
            with self.subTest(source=source):
                self.assertEqual(format_json(source), source + "\n")

    def test_four_space_indent(self):
        self.assertEqual(format_json('{"a":[1]}', indent=4), '{\n    "a": [\n        1\n    ]\n}\n')

    def test_repeated_keys_are_rejected_including_escaped_aliases(self):
        for source in ('{"a":1,"a":2}', '{"x":{"a":1,"a":2}}', '{"a":1,"\\u0061":2}'):
            with self.subTest(source=source), self.assertRaisesRegex(JsonError, "duplicate object key"):
                parse_json(source)

    def test_non_standard_numbers_are_rejected(self):
        for source in ("NaN", "Infinity", "-Infinity", "[NaN]"):
            with self.subTest(source=source), self.assertRaisesRegex(JsonError, "non-standard"):
                parse_json(source)

    def test_invalid_syntax_reports_location(self):
        for source in ("", "{", "[1,]", '{"a":01}', "{} {}", "// comment\n{}", '"unescaped\nline"'):
            with self.subTest(source=source), self.assertRaisesRegex(JsonError, r"line \d+, column \d+"):
                parse_json(source)

    def test_utf8_bom_is_accepted(self):
        self.assertEqual(format_json('\ufeff{"a":1}', compact=True), '{"a":1}\n')

    def test_lone_surrogates_stay_escaped(self):
        self.assertEqual(format_json('"\\ud800"'), '"\\ud800"\n')

    def test_deep_nesting_has_a_controlled_error(self):
        # Decoder depth varies across Python releases; rendering is recursive.
        with self.assertRaisesRegex(JsonError, "too deep"):
            format_json("[" * 10000 + "0" + "]" * 10000)


if __name__ == "__main__":
    unittest.main()
