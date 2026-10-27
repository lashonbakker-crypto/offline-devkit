"""Expand home-relative paths with a controlled input error on lookup failure."""

from pathlib import Path


def expand_user(path: Path | str) -> Path:
    value = Path(path)
    try:
        return value.expanduser()
    except RuntimeError as error:
        raise ValueError(f"cannot expand user path {str(value)!r}: {error}") from error
