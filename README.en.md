# Offline DevKit

[![Tests](https://github.com/lashonbakker-crypto/offline-devkit/actions/workflows/ci.yml/badge.svg)](https://github.com/lashonbakker-crypto/offline-devkit/actions/workflows/ci.yml)

**Local JSON / JSONL checks. Exact JSON numbers. Read-only file reports.**

[中文](README.md) · [Download](https://github.com/lashonbakker-crypto/offline-devkit/releases/latest) · [Command reference](docs/usage.md) · [Contributing](CONTRIBUTING.md)

A Python standard-library CLI for config files, JSONL datasets and logs, downloads, and backups. **Python 3.10+ · Zero third-party runtime dependencies · MIT.** All processing happens locally and the tools make no network requests.

| Command | Purpose | Detail |
| --- | --- | --- |
| `json` | Validate or format UTF-8 JSON | Preserves numeric tokens exactly; rejects duplicate keys and NaN/Infinity |
| `jsonl` | Check JSONL / NDJSON records | Physical line numbers, bounded reads; explicit `--gzip` supports compressed logs |
| `dupes` | Find duplicate file content | Size/SHA-256 filtering, optional byte verification, hard-link handling |
| `sizes` | Inspect logical file sizes | Top-level directory totals and largest files; JSON output available |

## See it in 30 seconds

![Actual CLI output: exact JSON numbers, JSONL errors, and duplicate files](assets/demo.gif)

The demo uses the included fixtures and actual CLI output. [Reproduce it](docs/demo.md). If it helps, **Star** the repo to keep it handy. Feedback about real workflows is welcome.

## Quick start

**Single-file option:** download `offline-devkit.pyz` from [Releases](https://github.com/lashonbakker-crypto/offline-devkit/releases/latest). Python 3.10+ is the only requirement; pip and build tools are unnecessary:

```bash
python offline-devkit.pyz --help
python offline-devkit.pyz sizes . --top 5
```

Verify the downloaded file with the [SHA-256 instructions](docs/publishing.md).

Starting with v0.4.0, check gzip JSONL / NDJSON directly:

```bash
python offline-devkit.pyz jsonl records.jsonl.gz --gzip --json
```

Decompression requires `--gzip`; filenames do not enable it automatically. Line numbers and record byte limits apply after decompression. Truncated streams, CRC and compression-format failures set `complete=false` and return 2 even if all previously checked records were valid. See the [bilingual gzip guide](docs/05-gzip-jsonl.md).

Use `py -3` on Windows or `python3` on macOS / Linux when needed. Downloading requires network access; subsequent execution is offline.

**Source option:** clone or extract the repository, then try the included fixtures:

```bash
git clone https://github.com/lashonbakker-crypto/offline-devkit.git
cd offline-devkit
python -m offline_devkit json examples/config.json
python -m offline_devkit jsonl examples/records.jsonl
python -m offline_devkit dupes examples/files
python -m offline_devkit sizes examples/files --top 3
```

Cloning needs network access; extracting a source ZIP works too. The tool commands above do not need network access.

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
python -m offline_devkit jsonl examples/records.jsonl
python -m offline_devkit jsonl examples/invalid-records.jsonl --json
python -m offline_devkit dupes ./Downloads --min-size 1024 --exclude "*.tmp"
python -m offline_devkit dupes ./Downloads --verify-bytes --json
python -m offline_devkit sizes . --top 10 --json
```

JSON input is limited to 16 MiB, accepts one leading UTF-8 BOM (repeated BOMs are rejected), and retains exact number spellings including exponents and negative zero. Formatting may change whitespace and string escapes. Duplicate keys are checked after escape decoding.

Command output uses UTF-8 and LF newlines, including redirected output on Windows. Validation and formatting may support different nesting depths because Python decoder and recursion limits vary; exceeding those limits produces a controlled error.

`jsonl` checks one JSON value per physical line. It accepts CRLF and an optional final newline, and rejects blank lines, BOMs, invalid UTF-8, duplicate keys, and non-standard numbers. By default a record is limited to 1 MiB excluding LF/CRLF, and only the first 20 errors are retained while every line is checked. Adjust these limits with `--max-line-bytes` and `--max-errors`. Invalid records or an incomplete read return 2. The JSON report includes `complete` and `errors_omitted` so a partial read or an abbreviated error sample is explicit. Empty input has zero records. This validates syntax and this tool's strict rules, rather than application schemas or a particular AI provider's dataset requirements. Input is plain by default; use `--gzip` for gzip files or binary stdin.

File operations are read-only. Symlinks and Windows reparse points are skipped. Dependency/cache directories are excluded by default; use `--include-ignored` to include them. `--exclude` is a repeatable, case-sensitive glob matched against a basename or root-relative path.

For stdin, use the [Bash / PowerShell pipeline recipes](docs/04-jsonl-pipelines.en.md). They retain both producer and validator exit codes, set UTF-8 explicitly, and show why a producer failure can coexist with valid records.

## Exit codes and limits

- `0`: complete; ordinary duplicate reports return 0 even when duplicates exist.
- `1`: duplicates found when `dupes --fail-if-found` is set.
- `2`: invalid input, invalid arguments, or an incomplete scan/read.
- `130`: interrupted.

Reports measure logical file sizes, not allocated or reclaimable disk space. Inventory counts hard-link paths separately; duplicate estimates count each file identity once. SHA-256 matches are the default duplicate evidence. Add `dupes --verify-bytes` to compare same-hash candidates in bounded chunks; the extra pass is slower and still is not a filesystem snapshot.

Scan stable, trusted directories. This is not a filesystem snapshot or an isolation boundary against concurrent hostile changes. Reported paths can be sensitive. Do not redirect JSON output to its input file or place scan output inside the scanned directory.

Queued directories are checked before entry and after listing. An observed replacement by a link or another directory is skipped, recorded in `errors`, and returns exit code 2. These path-based checks still have gaps between checking and use, do not fully guard ancestor replacements, and cannot reliably identify ordinary directory replacements without usable device/inode metadata.

## Development

```bash
python -m unittest discover -s tests -v
```

CI covers Linux / Python 3.10, 3.12, 3.14 and Windows and macOS 15 (Intel) / Python 3.12. It checks behavior, installation, and the portable archive. **Use the badge and [Actions](https://github.com/lashonbakker-crypto/offline-devkit/actions) for the current commit's result.**

Build the single-file archive using only the standard library:

```bash
python scripts/build_zipapp.py
python dist/offline-devkit.pyz --help
```

The archive contains the Python sources, an entry point that preserves exit codes, and the MIT license. It does not bundle a Python interpreter. The tests run it outside the source directory with isolated Python imports.

The Chinese technical notes explain [lossless JSON numbers](docs/01-json-numbers.md) and [duplicate discovery](docs/02-duplicates.md). See the [roadmap](ROADMAP.md), [changelog](CHANGELOG.md), and [official references](docs/references.md).

Original code and documentation, licensed under [MIT](LICENSE).
