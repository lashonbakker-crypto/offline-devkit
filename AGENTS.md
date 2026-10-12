# Repository guidance

This repository is a small, read-only Python CLI and educational source project.

- Support Python 3.10+. Use only the standard library at runtime.
- Keep file commands read-only. Do not add deletion, overwrite, networking, or credential handling implicitly.
- Preserve JSON numeric tokens and reject duplicate keys and NaN/Infinity.
- Do not follow symlinks or Windows reparse points intentionally. Document concurrency limits accurately.
- Do not describe logical file sizes as allocated or reclaimable disk space.
- Keep report order deterministic. Report incomplete scans with nonzero status.
- Run `python -m unittest discover -s tests -v` after relevant code changes.
- Add regression tests for meaningful behavior changes, not to increase the test count.
- Update command documentation and CHANGELOG when public behavior changes.
- Never claim cross-platform CI passed until actual workflow results have been inspected.
- Main README is Chinese; keep README.en.md aligned for user-facing behavior.
- Do not commit caches, generated builds, local reports, credentials, or personal data.
