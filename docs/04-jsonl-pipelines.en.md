# Check a JSONL producer with Bash or PowerShell

[中文](04-jsonl-pipelines.md) · [Command reference](usage.md)

Run these recipes from the repository root with Python 3.10+. A pipe sends the producer's standard output to the validator's standard input. Diagnostics use standard error so they do not become JSONL records.

The synthetic [producer](../examples/produce_jsonl.py) emits four UTF-8 records without a BOM: a greeting, a record containing `城市` and `南京 café`, an exact `1E-400` number, and `null`. `--invalid` duplicates the `城市` key on physical line 2 using its escaped equivalent. `--fail` emits two valid records, writes a diagnostic to stderr, then exits 3.

| Scenario | Lines | Valid / invalid | Producer exit | Validator exit | Recipe exit |
| --- | --- | --- | --- | --- | --- |
| `valid` | 4 | 4 / 0 | 0 | 0 | 0 |
| `invalid` | 4 | 3 / 1 | 0 | 2 | 2 |
| `producer-failure` | 2 | 2 / 0 | 3 | 0 | 3 |

All three reports have `complete=true`: the validator reached EOF on the pipe. This does not prove the producer emitted its intended dataset. Always preserve both exit codes. A producer failure takes precedence; otherwise the recipe returns the validator's code.

## Bash

```bash
bash scripts/check_jsonl_pipeline.sh valid
bash scripts/check_jsonl_pipeline.sh invalid
bash scripts/check_jsonl_pipeline.sh producer-failure
```

The [script](../scripts/check_jsonl_pipeline.sh) prints its JSON report to stdout and both exit codes to stderr. It captures Bash's `PIPESTATUS` immediately after the pipeline, before any other command can replace that array. Index 0 is the producer; index 1 is the validator. `$?` alone supplies only a combined status. The script enables `pipefail` and disables `errexit` in its own process so it can inspect expected nonzero results. A parent script using `set -e` should invoke expected failures inside a conditional.

For a valid input only, the underlying pipe is:

```bash
python3 examples/produce_jsonl.py | python3 -m offline_devkit jsonl --json
```

The recipe defaults to `python3`; set `DEVKIT_PYTHON` to a virtual environment's interpreter if necessary. Both commands must use the same Python environment. The command array always contains the interpreter and script path, avoiding Bash 3.2's empty-array expansion problem under `set -u` on macOS.

## PowerShell 7

```powershell
pwsh -NoProfile -File scripts/check_jsonl_pipeline.ps1 -Mode valid
pwsh -NoProfile -File scripts/check_jsonl_pipeline.ps1 -Mode invalid
pwsh -NoProfile -File scripts/check_jsonl_pipeline.ps1 -Mode producer-failure
```

Use `pwsh`, not Windows PowerShell 5.1; no validation is claimed for 5.1. The [script](../scripts/check_jsonl_pipeline.ps1) defaults to `python`; its `-Python` parameter accepts an interpreter path. The parent PowerShell can immediately save `$LASTEXITCODE` after each invocation.

It explicitly sets `$OutputEncoding` and console input/output encoding to BOM-free UTF-8. A script block wraps the producer and saves its `$LASTEXITCODE` in script scope before forwarding records to the validator. Immediately after the pipe, it saves the validator's `$LASTEXITCODE`. It disables automatic promotion of expected native failures, restores encoding settings in `finally`, and runs in a fresh process without a user's profile. It does not rely on default `Get-Content` / `Out-File` encoding. Bash's `PIPESTATUS` syntax is not portable to PowerShell.

## Reproduce the checks

```bash
python scripts/verify_jsonl_pipelines.py --shell bash
```

```powershell
python scripts/verify_jsonl_pipelines.py --shell powershell
```

The verifier runs the actual shell and fails explicitly if it is missing. It checks all three process exit codes, both native statuses, counts, EOF state, the UTF-8 duplicate key on line 2, and unchanged hashes of the example files. The Chinese key also detects text corruption while passing through the pipeline.

Local validation passed on Linux / Python 3.12.14 / Bash 5.2.21. The three Windows / Python 3.12.10 / PowerShell 7.6.6 cases also passed in [actual CI](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38346713159). That run exposed the macOS / Bash 3.2.57 empty-array issue; the script now uses a nonempty command array, with the fix subject to its own commit's CI. Each run prints actual shell and Python versions.

After running the examples, explain why a syntactically valid partial stream can coexist with an overall failure, where each shell captures both statuses, and what `complete` actually means. Then read [jsonl_tools.py](../offline_devkit/jsonl_tools.py) and [cli.py](../offline_devkit/cli.py).

Official references: [Bash pipelines](https://www.gnu.org/software/bash/manual/html_node/Pipelines.html), [Bash variables](https://www.gnu.org/software/bash/manual/html_node/Bash-Variables.html), [PowerShell encoding preferences](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables), and [PowerShell automatic variables](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_automatic_variables).
