"""A parser for Clausewitz script, the format of the game files under common/.

The save parser (rust_parser) reads save files only: it fails on comments, comparison
operators and @variables, which game files use everywhere. Game files are small, so a
plain Python parser is fast enough, and the result is cached per game version.

Representation: a block is a dict. A key that repeats becomes a list of its values.
A bare value list ("{ a b c }") becomes a list. Comparison operators other than "="
are kept in the key, e.g. "num_pops>" → 5, so conditions stay distinguishable from
assignments. @variables are substituted when they are defined in the same file or in
common/scripted_variables; inline maths "@[ ... ]" is evaluated for + - * / only.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
    |(?P<comment>\#[^\n]*)
    |(?P<string>"(?:[^"\\]|\\.)*")
    |(?P<math>@\\?\[[^\]]*\])
    |(?P<op>>=|<=|!=|==|\?=|[=<>{}])
    |(?P<word>(?:[^\s=<>{}"\#!?]|[?!](?!=))+)
    """,
    re.VERBOSE,
)


class ScriptError(ValueError):
    pass


def tokenize(text: str) -> Iterator[str]:
    pos = 0
    length = len(text)
    while pos < length:
        match = _TOKEN.match(text, pos)
        if not match:
            raise ScriptError(f"unexpected character {text[pos]!r} at {pos}")
        pos = match.end()
        kind = match.lastgroup
        if kind in ("ws", "comment"):
            continue
        token = match.group(kind)
        if kind == "string":
            yield "\0" + token[1:-1]  # mark strings so "{" in quotes is not a brace
        else:
            yield token


def _atom(token: str, variables: Mapping[str, Any]) -> Any:
    if token.startswith("\0"):
        return token[1:]
    if token.startswith("@[") or token.startswith("@\\["):
        return _evaluate(token[token.index("[") + 1 : -1], variables)
    if token.startswith("@") and token[1:] in variables:
        return variables[token[1:]]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return token


_MATH_SAFE = re.compile(r"^[\d\s.+\-*/()]+$")


def _evaluate(expr: str, variables: Mapping[str, Any]) -> Any:
    def substitute(match: re.Match[str]) -> str:
        name = match.group(0)
        return str(variables.get(name, variables.get(name.lstrip("@"), name)))

    expanded = re.sub(r"@?[A-Za-z_][A-Za-z0-9_]*", substitute, expr)
    if not _MATH_SAFE.match(expanded):
        return "@[" + expr + "]"
    value = eval(expanded, {"__builtins__": {}}, {})  # digits and operators only
    return int(value) if float(value).is_integer() else value


def _add(block: dict[str, Any], key: str, value: Any) -> None:
    if key in block:
        existing = block[key]
        if isinstance(existing, _Repeated):
            existing.append(value)
        else:
            block[key] = _Repeated([existing, value])
    else:
        block[key] = value


class _Repeated(list):
    """Marks a list built from a repeated key, as opposed to a bare value list."""


def parse(text: str, variables: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Parse script text. File-level @definitions are collected into the variables."""
    scope = dict(variables or {})
    tokens = list(tokenize(text))
    block, index = _parse_block(tokens, 0, scope, top=True)
    return block


def _parse_block(tokens: list[str], index: int, scope: dict[str, Any], top: bool = False):
    block: dict[str, Any] = {}
    bare: list[Any] = []
    length = len(tokens)
    while index < length:
        token = tokens[index]
        if token == "}":
            if top:
                index += 1  # stray closing brace: the game tolerates it, so do we
                continue
            return (block if block or not bare else bare), index + 1
        if token == "{":
            # anonymous block inside a list, e.g. "{ { a } { b } }"
            value, index = _parse_block(tokens, index + 1, scope)
            bare.append(value)
            continue
        next_token = tokens[index + 1] if index + 1 < length else None
        if next_token in ("=", "==", "?=", "<", ">", "<=", ">=", "!="):
            op = next_token
            value_token = tokens[index + 2] if index + 2 < length else None
            if value_token is None:
                raise ScriptError(f"missing value after {token} {op}")
            if value_token == "{":
                value, index = _parse_block(tokens, index + 3, scope)
            else:
                value = _atom(value_token, scope)
                index += 3
            key = token[1:] if token.startswith("\0") else token
            if key.startswith("@") and op == "=":
                scope[key[1:]] = value
                continue
            if op not in ("=", "==", "?="):
                key = key + op
            _add(block, key, value)
        else:
            bare.append(_atom(token, scope))
            index += 1
    if not top:
        raise ScriptError("unclosed block")
    return block, index


def parse_file(path: Path, variables: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return parse(path.read_text(encoding="utf-8-sig", errors="replace"), variables)


def as_list(value: Any) -> list[Any]:
    """Values of a key that may or may not repeat."""
    if value is None:
        return []
    if isinstance(value, _Repeated):
        return list(value)
    return [value]
