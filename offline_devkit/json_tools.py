"""Validate JSON strictly and format it without converting numeric tokens."""

import json
from typing import Any


class JsonError(ValueError):
    """The input cannot be processed as strict JSON."""


class _Number(str):
    """An already-validated JSON number, retaining its exact spelling."""


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise JsonError(f"duplicate object key: {key!r}")
        result[key] = value
    return result


def _constant(token: str) -> None:
    raise JsonError(f"non-standard JSON number: {token}")


def parse_json(text: str) -> Any:
    """Reject repeated keys and NaN/Infinity; preserve every numeric literal."""
    try:
        return json.loads(
            text.removeprefix("\ufeff"),
            parse_int=_Number,
            parse_float=_Number,
            parse_constant=_constant,
            object_pairs_hook=_object,
        )
    except json.JSONDecodeError as error:
        raise JsonError(
            f"line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error
    except RecursionError as error:
        raise JsonError("JSON nesting is too deep for this Python runtime") from error


def _quote(value: str) -> str:
    # Keep readable Unicode; escape lone surrogates accepted by json.loads.
    return (
        json.dumps(value, ensure_ascii=False)
        .encode("utf-8", errors="backslashreplace")
        .decode("utf-8")
    )


def format_json(
    text: str, *, indent: int = 2, sort_keys: bool = False, compact: bool = False
) -> str:
    """Return strict JSON plus one newline, retaining number tokens exactly."""
    if indent not in (2, 4):
        raise ValueError("indent must be 2 or 4")
    value = parse_json(text)

    def render(item: Any, level: int) -> str:
        if isinstance(item, _Number):
            return str(item)
        if item is None:
            return "null"
        if isinstance(item, bool):
            return "true" if item else "false"
        if isinstance(item, str):
            return _quote(item)
        if isinstance(item, list):
            opening, closing = "[", "]"
            children = [render(child, level + 1) for child in item]
        else:
            opening, closing = "{", "}"
            keys = sorted(item) if sort_keys else item
            separator = ":" if compact else ": "
            children = [
                _quote(key) + separator + render(item[key], level + 1)
                for key in keys
            ]
        if not children:
            return opening + closing
        if compact:
            return opening + ",".join(children) + closing
        padding = " " * indent * (level + 1)
        inner = (",\n" + padding).join(children)
        return opening + "\n" + padding + inner + "\n" + " " * indent * level + closing

    try:
        return render(value, 0) + "\n"
    except RecursionError as error:
        raise JsonError("JSON nesting is too deep to format") from error
