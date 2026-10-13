#!/usr/bin/env bash
# Run from the repository root; preserve both native commands' exit codes.
set -u
set -o pipefail
set +e

devkit_python="${DEVKIT_PYTHON:-python3}"
producer_args=()
case "${1:-valid}" in
    valid) ;;
    invalid) producer_args=(--invalid) ;;
    producer-failure) producer_args=(--fail) ;;
    *) printf 'Usage: bash scripts/check_jsonl_pipeline.sh [valid|invalid|producer-failure]\n' >&2; exit 2 ;;
esac

"$devkit_python" examples/produce_jsonl.py "${producer_args[@]}" |
    "$devkit_python" -m offline_devkit jsonl --json
# This must be the first command after the pipeline: another command replaces it.
pipeline_codes=("${PIPESTATUS[@]}")
printf 'producer_exit=%s validator_exit=%s\n' "${pipeline_codes[0]}" "${pipeline_codes[1]}" >&2
if (( pipeline_codes[0] != 0 )); then
    exit "${pipeline_codes[0]}"
fi
exit "${pipeline_codes[1]}"
