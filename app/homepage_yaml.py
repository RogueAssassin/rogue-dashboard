"""Small YAML reader for Homepage's configuration subset.

It intentionally supports only indentation-based mappings, sequences and
scalar values used by Homepage configuration. It is not a general YAML loader
and never constructs Python objects or executes tags.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


@dataclass(frozen=True)
class Line:
    indent: int
    value: str
    number: int


def _strip_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in ("'", '"'):
            quote = None if quote == char else char if quote is None else quote
            continue
        if char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.rstrip()


def _tokenise(text: str) -> list[Line]:
    result: list[Line] = []
    for number, raw in enumerate(text.replace("\t", "    ").splitlines(), 1):
        value = _strip_comment(raw)
        if not value.strip() or value.strip() == "---":
            continue
        indent = len(value) - len(value.lstrip(" "))
        result.append(Line(indent, value.strip(), number))
    return result


def _split_mapping(value: str, line_number: int) -> tuple[str, str]:
    quote: str | None = None
    depth = 0
    for index, char in enumerate(value):
        if char in ("'", '"'):
            quote = None if quote == char else char if quote is None else quote
            continue
        if quote is not None:
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth = max(0, depth - 1)
        elif char == ":" and depth == 0:
            key = value[:index].strip()
            if not key:
                raise ValueError(f"Missing mapping key on line {line_number}")
            return _scalar(key), value[index + 1 :].strip()
    raise ValueError(f"Expected a mapping on line {line_number}")


def _scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return None
    if value.startswith("{{") and value.endswith("}}"):
        return value
    if value[0:1] == value[-1:] and value.startswith(("'", '"')):
        if value.startswith('"'):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value[1:-1]
        return value[1:-1].replace("''", "'")
    lowered = value.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", value):
        return float(value)
    if value == "[]":
        return []
    if value == "{}":
        return {}
    return value


class Parser:
    def __init__(self, lines: list[Line]):
        self.lines = lines

    def parse(self) -> Any:
        if not self.lines:
            return None
        value, index = self._block(0, self.lines[0].indent)
        if index != len(self.lines):
            line = self.lines[index]
            raise ValueError(f"Unexpected indentation on line {line.number}")
        return value

    def _block(self, index: int, indent: int) -> tuple[Any, int]:
        if self.lines[index].value.startswith("- ") or self.lines[index].value == "-":
            return self._sequence(index, indent)
        return self._mapping(index, indent)

    def _sequence(self, index: int, indent: int) -> tuple[list[Any], int]:
        result: list[Any] = []
        while index < len(self.lines):
            line = self.lines[index]
            if line.indent != indent or not (line.value.startswith("- ") or line.value == "-"):
                break
            body = line.value[1:].strip()
            index += 1
            if not body:
                if index < len(self.lines) and self.lines[index].indent > indent:
                    item, index = self._block(index, self.lines[index].indent)
                else:
                    item = None
                result.append(item)
                continue
            if ":" not in body:
                result.append(_scalar(body))
                continue
            key, raw = _split_mapping(body, line.number)
            item: dict[str, Any] = {}
            if raw:
                item[str(key)] = _scalar(raw)
                if index < len(self.lines) and self.lines[index].indent > indent:
                    extra, index = self._block(index, self.lines[index].indent)
                    if not isinstance(extra, dict):
                        raise ValueError(f"Expected mapping after line {line.number}")
                    item.update(extra)
            elif index < len(self.lines) and self.lines[index].indent > indent:
                item[str(key)], index = self._block(index, self.lines[index].indent)
            else:
                item[str(key)] = None
            result.append(item)
        return result, index

    def _mapping(self, index: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(self.lines):
            line = self.lines[index]
            if line.indent != indent or line.value.startswith("- ") or line.value == "-":
                break
            key, raw = _split_mapping(line.value, line.number)
            index += 1
            if raw:
                result[str(key)] = _scalar(raw)
            elif index < len(self.lines) and self.lines[index].indent > indent:
                result[str(key)], index = self._block(index, self.lines[index].indent)
            else:
                result[str(key)] = None
        return result, index


def loads(text: str) -> Any:
    if len(text.encode("utf-8")) > 1_000_000:
        raise ValueError("YAML file exceeds the 1 MB safety limit")
    return Parser(_tokenise(text)).parse()
