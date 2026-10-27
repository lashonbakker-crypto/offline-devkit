# Offline DevKit

[![Tests](https://github.com/lashonbakker-crypto/offline-devkit/actions/workflows/ci.yml/badge.svg)](https://github.com/lashonbakker-crypto/offline-devkit/actions/workflows/ci.yml)

**Catch invalid JSONL records, duplicate keys, and broken gzip streams before import. Data stays local.**

[中文](README.md) · [Download](https://github.com/lashonbakker-crypto/offline-devkit/releases/latest) · [Command reference](docs/usage.md) · [Contributing](CONTRIBUTING.md)

A CLI for developers importing JSONL / NDJSON datasets or processing compressed logs. Locate invalid records by physical line and distinguish bad records from incomplete input. **Python 3.10+ · Zero third-party runtime dependencies · MIT.** It also preserves JSON number spellings and provides read-only duplicate-file and size reports. All processing is local.

Checks cover syntax, duplicate keys, and read integrity; they do not validate application schemas or guarantee acceptance by a particular import service.

| Command | Purpose | Detail |
| --- | --- | --- |
| `jsonl` | Check JSONL / NDJSON records | Physical line numbers, bounded reads; explicit `--gzip` supports compressed logs |
| `json` | Validate or format UTF-8 JSON | Preserves numeric tokens exactly; rejects duplicate keys and NaN/Infinity |
| `dupes` | Find duplicate file content | Size/SHA-256 filtering, optional byte verification, hard-link handling |
| `sizes` | Inspect logical file sizes | Top-level directory totals and largest files; JSON output available |

## See it in 30 seconds

![Actual CLI output: exact JSON numbers, JSONL errors, and duplicate files](assets/demo.gif)

The demo uses the included fixtures and actual CLI output. [Reproduce it](docs/demo.md). If it helps, **Star** the repo to keep it handy. Feedback about real workflows is welcome.

## Quick start

**See three real outcomes first.** With Git and Python 3.10+, run these three commands. No pip or personal data is needed:

```bash
git clone https://github.com/lashonbakker-crypto/offline-devkit.git
cd offline-devkit
python scripts/try_jsonl.py
```

| Case | Validator exit | Expected result |
| --- | --- | --- |
| Complete gzip with three valid records | `0` | `valid=3; invalid=0; complete=true` |
| Duplicate key on line 2, including an escaped spelling | `2` | `valid=2; invalid=1; complete=true`; error points to line 2 |
| Truncated gzip trailer | `2` | `complete=false`; any counts are partial |

The demo invokes the actual CLI, creates and cleans synthetic samples in a temporary directory, and checks results and input hashes. It reads no personal files and creates no extracted files. `Demo passed` and the demo's exit 0 mean both bad inputs were correctly rejected with exit 2. Partial counters on truncation can vary by Python version; check `complete=false`.

Cloning requires network access; the subsequent demo runs locally. Without Git, extract the [main branch source ZIP](https://github.com/lashonbakker-crypto/offline-devkit/archive/refs/heads/main.zip) and run the last command from its directory; older source releases do not contain the new demo script. Use `py -3` on Windows or `python3` on macOS / Linux if needed.

Already using `json.loads`? Run `python scripts/compare_json_checks.py` to see overwritten fields, accepted NaN and changed number spellings side by side. The [three-case comparison and selection guide](docs/08-json-defaults.md#english) explains the scope; Python can implement the same policies through hooks, and this compares only its defaults.

**Check your own files.** From the source directory, replace the paths with existing files:

```bash
python -m offline_devkit jsonl records.jsonl --json
python -m offline_devkit jsonl records.jsonl.gz --gzip --json
```

**Carry one file.** Download `offline-devkit.pyz` from [Releases](https://github.com/lashonbakker-crypto/offline-devkit/releases/latest), verify it using the [SHA-256 instructions](docs/publishing.md), and run:

```bash
python offline-devkit.pyz jsonl records.jsonl.gz --gzip --json
```

Python 3.10+ is required, with no pip or build tools. Gzip support is available from v0.4.0. It requires explicit `--gzip`; filenames do not enable decompression. **Previously read records can all be valid while a truncated compressed stream still fails.** Line numbers and record limits apply after decompression. See the [bilingual gzip guide](docs/05-gzip-jsonl.md).

Other tools can run directly from source too:

```bash
python -m offline_devkit json examples/config.json
python -m offline_devkit dupes examples/files
python -m offline_devkit sizes examples/files --top 3
```

The included files contain one duplicate group. Tool commands run offline.

Optional installation in an activated virtual environment:

```bash
python -m pip install .
offline-devkit --help
```

Installation may download the setuptools build dependency. Running the tools afterwards, or directly from source, is offline. This project does not currently promise a published PyPI package.

## Check data on each commit

Copy the two-file [GitHub Actions recipe](docs/07-github-actions.md#english) into your repository and select one JSONL or gzip dataset. Duplicate keys, truncated gzip, and missing files make the job fail; configure a required status check separately to make it a merge condition.

The recipe pins the published v0.4.0 archive and checks its hardcoded SHA-256 before execution, with no pip dependency. Preparing the tool needs network access; data checks run locally on the runner. Try `python scripts/verify_ci_recipe.py` first for seven disposable verification cases.

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

The v0.4.1 source reduces temporary allocations when selecting a small largest-file list. The [reproducible benchmark](docs/06-largest-files.md) measures report construction over already allocated synthetic metadata, excluding filesystem scans, input allocation, process RSS, and CLI startup. Run `python scripts/benchmark_size_report.py --counts 1000 10000 100000 --top 10 --repeats 5`; it verifies results against full sorting and emits timing samples, traced allocation peaks, and complete-report hashes. Check [Releases](https://github.com/lashonbakker-crypto/offline-devkit/releases/latest) for published versions and assets; v0.4.0 does not include this optimization. Full directory inventory still uses memory proportional to the number of files, and large `--top` values are not guaranteed to be faster.

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
