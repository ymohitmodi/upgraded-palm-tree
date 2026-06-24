"""A tiny, dependency-free YAML *subset* parser.

NYX must run on a bare mini-PC with nothing but the standard library, yet the
Constitution is authored in friendly YAML. This parser supports exactly the
subset the project uses:

  * nested mappings (indentation-based)
  * sequences of scalars and of mappings (``- key: value`` blocks)
  * inline flow lists ``[a, b, c]``
  * block scalars ``|`` (literal, multi-line)
  * scalars: str (quoted/unquoted), int, float, bool, null, dates-as-str

If PyYAML is installed, :func:`nyx.constitution.load_yaml` prefers it; this
module is the zero-dependency fallback so the factory is never blocked.

It is deliberately small, not a conformant YAML 1.2 implementation.
"""
from __future__ import annotations

import re
from typing import Any

_KEY_RE = re.compile(r"^[\w.\-]+:(\s|$)")


class MiniYAMLError(ValueError):
    """Raised when the input falls outside the supported YAML subset."""


class _Parser:
    def __init__(self, text: str) -> None:
        self.lines: list[str] = text.replace("\t", "  ").splitlines()
        self.i = 0

    # -- line helpers --------------------------------------------------------
    def _skip_blank(self) -> None:
        while self.i < len(self.lines):
            s = self.lines[self.i].strip()
            if s == "" or s.startswith("#"):
                self.i += 1
            else:
                break

    @staticmethod
    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def _peek_indent(self) -> int | None:
        self._skip_blank()
        if self.i >= len(self.lines):
            return None
        return self._indent(self.lines[self.i])

    # -- node dispatch -------------------------------------------------------
    def parse_node(self, indent: int) -> Any:
        cur = self._peek_indent()
        if cur is None or cur < indent:
            return None
        line = self.lines[self.i].strip()
        if line == "-" or line.startswith("- "):
            return self.parse_sequence(cur)
        return self.parse_mapping(cur)

    def parse_mapping(self, indent: int) -> dict:
        result: dict[str, Any] = {}
        while True:
            cur = self._peek_indent()
            if cur is None or cur < indent:
                break
            if cur > indent:
                raise MiniYAMLError(f"unexpected indent on line {self.i + 1}")
            line = self.lines[self.i].strip()
            if ":" not in line:
                raise MiniYAMLError(f"expected mapping key on line {self.i + 1}: {line!r}")
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            self.i += 1
            result[key] = self._value_for(rest, indent)
        return result

    def parse_sequence(self, indent: int) -> list:
        items: list[Any] = []
        while True:
            cur = self._peek_indent()
            if cur is None or cur < indent:
                break
            if cur > indent:
                raise MiniYAMLError(f"unexpected indent on line {self.i + 1}")
            raw = self.lines[self.i]
            after = raw.strip()[1:].lstrip()  # drop leading '-'
            if after == "":
                # Nested block on following lines.
                self.i += 1
                items.append(self.parse_node(indent + 1))
            elif _KEY_RE.match(after):
                # Inline mapping item: rewrite "- " to "  " and parse a mapping
                # rooted at the key's column (indent + 2).
                dash = raw.index("-")
                self.lines[self.i] = raw[:dash] + " " + raw[dash + 1:]
                items.append(self.parse_mapping(indent + 2))
            elif after.startswith("["):
                items.append(self._flow_list(after))
                self.i += 1
            else:
                items.append(_scalar(after))
                self.i += 1
        return items

    def _value_for(self, rest: str, indent: int) -> Any:
        if rest == "":
            child_indent = self._peek_indent()
            if child_indent is not None and child_indent > indent:
                return self.parse_node(child_indent)
            return None
        if rest in ("|", "|-", "|+", ">", ">-", ">+"):
            return self._block_scalar(indent, fold=rest[0] == ">")
        if rest.startswith("["):
            return self._flow_list(rest)
        if rest.startswith("#"):
            return None
        # strip trailing inline comment for unquoted scalars
        return _scalar(rest)

    def _block_scalar(self, parent_indent: int, fold: bool) -> str:
        collected: list[str] = []
        base: int | None = None
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if line.strip() == "":
                collected.append("")
                self.i += 1
                continue
            if self._indent(line) <= parent_indent:
                break
            if base is None:
                base = self._indent(line)
            collected.append(line[base:])
            self.i += 1
        # drop trailing blank lines
        while collected and collected[-1] == "":
            collected.pop()
        sep = " " if fold else "\n"
        return sep.join(collected) if fold else "\n".join(collected)

    @staticmethod
    def _flow_list(text: str) -> list:
        inner = text.strip()
        if not (inner.startswith("[") and inner.endswith("]")):
            raise MiniYAMLError(f"malformed flow list: {text!r}")
        inner = inner[1:-1].strip()
        if inner == "":
            return []
        return [_scalar(part.strip()) for part in inner.split(",")]


def _scalar(token: str) -> Any:
    token = token.strip()
    # quoted
    if len(token) >= 2 and token[0] in "\"'" and token[-1] == token[0]:
        return token[1:-1]
    # strip trailing inline comment (unquoted only)
    if " #" in token:
        token = token.split(" #", 1)[0].strip()
    low = token.lower()
    if low in ("null", "~", ""):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if re.fullmatch(r"-?\d+\.\d+", token):
        return float(token)
    return token


def loads(text: str) -> Any:
    """Parse a YAML-subset document into Python objects."""
    parser = _Parser(text)
    parser._skip_blank()
    if parser.i >= len(parser.lines):
        return {}
    return parser.parse_node(parser._indent(parser.lines[parser.i]))
