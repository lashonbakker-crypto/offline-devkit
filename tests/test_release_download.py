"""Regression for Git's newline conversion during release-source export."""

import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.verify_release_download import export_release_source


@unittest.skipUnless(shutil.which("git"), "Git is needed for the optional source-ref export")
class ReleaseSourceTests(unittest.TestCase):
    def test_export_preserves_blob_bytes_with_windows_git_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository.git"
            configuration = root / "gitconfig"
            configuration.write_text("[core]\n\tautocrlf = true\n", encoding="utf-8")
            configuration_bytes = configuration.read_bytes()
            environment = dict(
                os.environ, GIT_CONFIG_GLOBAL=str(configuration), GIT_CONFIG_NOSYSTEM="1",
                GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
            )
            subprocess.check_output(
                ["git", "init", "--bare", "--quiet", str(repository)],
                env=environment, stderr=subprocess.PIPE,
            )

            def git(*arguments, data=None):
                return subprocess.check_output(
                    ["git", "-C", str(repository), *arguments],
                    input=data, env=environment, stderr=subprocess.PIPE,
                )

            content = b"First license line\nSecond license line\n"
            blob = git("hash-object", "-w", "--stdin", data=content).decode().strip()
            tree = git("mktree", data=f"100644 blob {blob}\tLICENSE\n".encode()).decode().strip()
            commit = git("commit-tree", tree, "-m", "synthetic newline fixture").decode().strip()
            git("update-ref", "refs/heads/main", commit)
            # Reproduce the actual failure: archive, as well as checkout,
            # converts the license when core.autocrlf=true is inherited.
            with zipfile.ZipFile(io.BytesIO(git("archive", "--format=zip", "refs/heads/main"))) as archive:
                self.assertEqual(archive.read("LICENSE"), content.replace(b"\n", b"\r\n"))
            destination = root / "export"
            destination.mkdir()
            with patch.dict(os.environ, environment):
                export_release_source(repository, destination, "refs/heads/main")
            self.assertEqual((destination / "LICENSE").read_bytes(), content)
            self.assertEqual(configuration.read_bytes(), configuration_bytes)
