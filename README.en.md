# Offline DevKit

[![Tests](https://github.com/lashonbakker-crypto/offline-devkit/actions/workflows/ci.yml/badge.svg)](https://github.com/lashonbakker-crypto/offline-devkit/actions/workflows/ci.yml)

**Small local tools. Readable code. Useful ideas to share.**

[中文](README.md) · [Command reference](docs/usage.md) · [Contributing](CONTRIBUTING.md)

A Python standard-library CLI for strict JSON validation and formatting, duplicate-file discovery, and directory size reports. It has no third-party runtime dependencies and makes no network requests.

| Command | Purpose | Detail |
| --- | --- | --- |
| `json` | Validate or format UTF-8 JSON | Preserves numeric tokens exactly; rejects duplicate keys and NaN/Infinity |
| `dupes` | Find duplicate file content | Groups by size, hashes in chunks with SHA-256, skips hard-link aliases |
| `sizes` | Inspect logical file sizes | Top-level directory totals and largest files; JSON output available |

## Quick start

Requires Python 3.10+. From the repository directory, run without installing:

```bash
git clone https://github.com/lashonbakker-crypto/offline-devkit.git
cd offline-devkit
python -m offline_devkit json examples/config.json
python -m offline_devkit dupes examples/files
python -m offline_devkit sizes examples/files --top 3
```

Cloning needs network access; extracting a source ZIP works too. The three tool commands above do not need network access.

Use `py -3` on Windows or `python3` on Unix when needed. The sample files contain one duplicate group.

Optional installation in an activated virtual environment:

```bash
python -m pip install .
offline-devkit --help
```

Installation may download the setuptools build dependency. Running the tools afterwards, or directly from source, is offline. This project does not currently promise a published PyPI package.

## Everyday examples

```bash
python -m offline_devkit json config.json --check
python -m offline_devkit json config.json --sort-keys > formatted.json
python -m offline_devkit dupes ./Downloads --min-size 1024 --exclude "*.tmp"
python -m offline_devkit sizes . --top 10 --json
```

JSON input is limited to 16 MiB, accepts a UTF-8 BOM, and retains exact number spellings including exponents and negative zero. Formatting may change whitespace and string escapes. Duplicate keys are checked after escape decoding.

Command output uses UTF-8 and LF newlines, including redirected output on Windows. Validation and formatting may support different nesting depths because Python decoder and recursion limits vary; exceeding those limits produces a controlled error.

File operations are read-only. Symlinks and Windows reparse points are skipped. Dependency/cache directories are excluded by default; use `--include-ignored` to include them. `--exclude` is a repeatable, case-sensitive glob matched against a basename or root-relative path.

## Exit codes and limits

- `0`: complete; ordinary duplicate reports return 0 even when duplicates exist.
- `1`: duplicates found when `dupes --fail-if-found` is set.
- `2`: invalid input, invalid arguments, or an incomplete scan/read.
- `130`: interrupted.

Reports measure logical file sizes, not allocated or reclaimable disk space. Inventory counts hard-link paths separately; duplicate estimates count each file identity once. SHA-256 matches are practical duplicate evidence, not a zero-collision proof. No byte-for-byte verification is performed.

Scan stable, trusted directories. This is not a filesystem snapshot or an isolation boundary against concurrent hostile changes. Reported paths can be sensitive. Do not redirect JSON output to its input file or place scan output inside the scanned directory.

Queued directories are checked before entry and after listing. An observed replacement by a link or another directory is skipped, recorded in `errors`, and returns exit code 2. These path-based checks still have gaps between checking and use, do not fully guard ancestor replacements, and cannot reliably identify ordinary directory replacements without usable device/inode metadata.

## Development

```bash
python -m unittest discover -s tests -v
```

Initial-release validation: 40 tests passed on Python 3.12 / Linux. The [pre-release CI run](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38272248834) passed behavior tests, installation, and command smoke checks on Linux / Python 3.10, 3.12, 3.14 and Windows, macOS / Python 3.12. The badge and Actions page show the status of subsequent commits.

The Chinese technical notes explain [lossless JSON numbers](docs/01-json-numbers.md) and [duplicate discovery](docs/02-duplicates.md). See the [roadmap](ROADMAP.md), [changelog](CHANGELOG.md), and [official references](docs/references.md).

Original code and documentation, licensed under [MIT](LICENSE).
