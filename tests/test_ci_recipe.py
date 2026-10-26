import importlib.util
import io
from contextlib import redirect_stderr, redirect_stdout
from http.client import IncompleteRead
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tested_ci_recipe", ROOT / "examples" / "github-actions" / "check_jsonl.py")
RECIPE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECIPE)


class ConsumerRecipeTests(unittest.TestCase):
    def test_incomplete_http_download_returns_two_without_executing(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "records.jsonl"
            source.write_bytes(b"{}\n")
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(RECIPE, "urlopen") as download, patch.object(RECIPE.subprocess, "run") as execute:
                download.return_value.__enter__.return_value.read.side_effect = IncompleteRead(b"partial", 10)
                with patch.object(sys, "argv", ["check_jsonl.py", str(source)]), redirect_stdout(output), redirect_stderr(errors):
                    status = RECIPE.main()
            self.assertEqual(status, 2)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("tool download failed", errors.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())
            execute.assert_not_called()
            self.assertEqual(source.read_bytes(), b"{}\n")


if __name__ == "__main__":
    unittest.main()
