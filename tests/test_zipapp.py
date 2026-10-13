import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ZipappTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.archive = cls.root / "offline-devkit.pyz"
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "build_zipapp.py"), str(cls.archive)],
            cwd=cls.root, capture_output=True, check=True,
        )

    def invoke(self, *args, data=b""):
        return subprocess.run(
            [sys.executable, "-I", str(self.archive), *args],
            input=data, capture_output=True, cwd=self.root,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), check=False,
        )

    def test_standalone_archive_preserves_json_numbers(self):
        result = self.invoke("json", "--compact", data=b'{"number":1E-400}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'{"number":1E-400}\n')

    def test_archive_propagates_error_exit_code(self):
        result = self.invoke("jsonl", "--json", data=b"{}\nNaN\n")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(json.loads(result.stdout)["errors"][0]["line"], 2)

    def test_archive_has_only_source_and_license(self):
        with zipfile.ZipFile(self.archive) as archive:
            files = [name for name in archive.namelist() if not name.endswith("/")]
        self.assertIn("LICENSE", files)
        self.assertIn("__main__.py", files)
        self.assertTrue(all(name == "LICENSE" or name.endswith(".py") for name in files))
        self.assertFalse(any("__pycache__" in name or ".git" in name for name in files))

    def test_archive_file_commands_work_outside_the_repository(self):
        directory = self.root / "files"
        directory.mkdir()
        for name in ("a.txt", "b.txt"):
            (directory / name).write_bytes(b"same")
        duplicates = self.invoke("dupes", str(directory), "--json")
        verified = self.invoke("dupes", str(directory), "--verify-bytes", "--json")
        sizes = self.invoke("sizes", str(directory), "--json")
        self.assertEqual(duplicates.returncode, 0, duplicates.stderr)
        self.assertEqual(json.loads(duplicates.stdout)["groups"][0]["paths"], ["a.txt", "b.txt"])
        self.assertEqual(verified.returncode, 0, verified.stderr)
        report = json.loads(verified.stdout)
        self.assertTrue(report["verify_bytes"])
        self.assertEqual(report["byte_comparisons"], 1)
        self.assertEqual(report["groups"][0]["verified_by"], "bytes")
        self.assertEqual(sizes.returncode, 0, sizes.stderr)
        self.assertEqual(json.loads(sizes.stdout)["total_bytes"], 8)


if __name__ == "__main__":
    unittest.main()
