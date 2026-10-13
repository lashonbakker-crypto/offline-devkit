"""Build a portable Python archive using only the standard library."""

import argparse
import shutil
import tempfile
import zipapp
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_archive(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        package = staging / "offline_devkit"
        package.mkdir()
        for source in sorted((REPO_ROOT / "offline_devkit").glob("*.py")):
            shutil.copyfile(source, package / source.name)
        shutil.copyfile(REPO_ROOT / "LICENSE", staging / "LICENSE")
        (staging / "__main__.py").write_text(
            "from offline_devkit.cli import main\n\nraise SystemExit(main())\n",
            encoding="utf-8",
        )
        zipapp.create_archive(staging, output, compressed=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path("dist/offline-devkit.pyz"))
    args = parser.parse_args()
    build_archive(args.output)
    print(f"Built {args.output} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
