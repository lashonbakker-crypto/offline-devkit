"""Emit synthetic UTF-8 records for the documented shell pipelines."""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--invalid", action="store_true", help="duplicate a key on line 2")
    mode.add_argument("--fail", action="store_true", help="fail after two valid records")
    args = parser.parse_args()
    records = [
        '{"id":1,"message":"Hello"}',
        '{"id":2,"城市":"南京 café"}',
        '{"id":3,"score":1E-400}',
        "null",
    ]
    if args.invalid:
        records[1] = '{"id":2,"城市":"南京","\\u57ce\\u5e02":"另一处"}'
    for record in records[:2] if args.fail else records:
        sys.stdout.buffer.write((record + "\n").encode("utf-8"))
    if args.fail:
        sys.stderr.write("synthetic producer failure after two records\n")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
