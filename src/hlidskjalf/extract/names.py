"""Display Names: rendering a save's name blocks with the game's localisation.

A name in the save is a block of a key plus optional variables, e.g.
    {"key": "NEW_COLONY_NAME_1", "variables": [{"key": "NAME", "value": {"key": "Menkar"}}]}
which the game shows as "Menkar Prime". The approach follows the NameRenderer of
stellaris-dashboard (MIT, eliasdoehne/stellaris-dashboard, game_info.py), with one
deliberate difference: nothing falls back to a prettified or raw key. A name we cannot
resolve raises UnresolvedName, because a wrong name in a Briefing is worse than none.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_LOC_LINE = re.compile(r'^\s*(?P<key>[^\s:#]+):\d*\s*"(?P<value>.*)"\s*(#.*)?$')
_VARIABLE = re.compile(r"\$(?P<key>[^$\s|]+?)(\|[^$]*)?\$")
_COLOUR = re.compile(r"§.")
_KEY_LIKE = re.compile(r"[A-Za-z0-9_.\-]+")
_PLAIN_WORD = re.compile(r"[A-Z][a-z'\-]+")
_ICON = re.compile(r"£[^£\s]+£?")


class UnresolvedName(ValueError):
    """A name block that the localisation cannot render."""


class Localisation:
    """Key → text table for one game language, built from .yml localisation files."""

    def __init__(self, entries: dict[str, str], adjective_suffixes: dict[str, str]):
        self.entries = entries
        # noun suffix → adjective template, from the adj_NN* keys ("a" → "*an")
        self.adjective_suffixes = adjective_suffixes

    @classmethod
    def from_files(cls, files: Iterable[Path]) -> Localisation:
        entries: dict[str, str] = {}
        adjectives: dict[str, str] = {}
        for path in files:
            with open(path, encoding="utf-8-sig") as handle:
                for line in handle:
                    match = _LOC_LINE.match(line)
                    if not match:
                        continue
                    key = match.group("key")
                    value = match.group("value").replace("\\n", "\n")
                    if key.startswith("adj_NN"):
                        suffix = key.removeprefix("adj_NN").lstrip("*")
                        adjectives[suffix] = value.split("|")[0]
                    else:
                        entries[key] = value
        return cls(entries, adjectives)

    def __contains__(self, key: str) -> bool:
        return key in self.entries

    def text(self, key: str) -> str:
        """The plain localised text for a key, with nested $references$ and colour codes
        resolved. Raises UnresolvedName for unknown keys."""
        if key not in self.entries:
            raise UnresolvedName(f"no localisation for key {key!r}")
        return _clean(self._expand_references(self.entries[key], depth=0))

    def text_or_none(self, key: str) -> str | None:
        return self.text(key) if key in self.entries else None

    def _expand_references(self, template: str, depth: int) -> str:
        if depth > 5:
            return template

        def replace(match: re.Match[str]) -> str:
            ref = match.group("key")
            if ref in self.entries:
                return self._expand_references(self.entries[ref], depth + 1)
            return match.group(0)

        return _VARIABLE.sub(replace, template)

    def render(self, name: Any) -> str:
        """Render a name block from the save into its Display Name."""
        return NameBlock(self).render(name)


def _clean(text: str) -> str:
    text = _COLOUR.sub("", text)
    text = _ICON.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip()


_ROMAN = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


def _roman(number: int) -> str:
    out = ""
    for value, symbol in _ROMAN:
        while number >= value:
            out += symbol
            number -= value
    return out


def _ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return f"{number}th"
    return f"{number}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th') }"


class NameBlock:
    """One rendering pass. Tags implement the grammar variants documented in the game's
    localisation/99_README_GRAMMAR.txt (sections 1–5), as far as names need them."""

    def __init__(self, loc: Localisation):
        self.loc = loc

    def render(self, name: Any, tags: set[str] | None = None, suffix: str = "") -> str:
        """suffix is appended to this block's template; %ADJ% uses it to pass its noun on."""
        if isinstance(name, str):
            name = {"key": name}
        if not isinstance(name, dict) or "key" not in name:
            raise UnresolvedName(f"not a name block: {name!r}")
        tags = set() if tags is None else tags
        key = name["key"]
        variables = _as_list(name.get("variables"))
        if name.get("literal") == "yes":
            if not suffix:
                return key
            template = key
        else:
            template = self._template(key, has_variables=bool(variables))

        if template == "%ADJ%":
            # "%ADJ%": the first variable is an adjective whose own template gets the
            # noun slot " $1$" appended, e.g. Interstellar + Empire → "Interstellar Empire".
            if not variables:
                raise UnresolvedName(f"%ADJ% without variables: {name!r}")
            return self.render(variables[0]["value"], tags, suffix=" $1$")
        template += suffix
        template, added = _pick_variant(template, tags)
        tags |= added

        if "value" in name:
            return self.render(name["value"], tags)

        values = [
            (var["key"], self.render(var["value"], tags))
            for var in variables
            if isinstance(var, dict) and "key" in var and "value" in var
        ]
        return _clean(self._substitute(template, values))

    def _template(self, key: str, has_variables: bool = False) -> str:
        if key == "%ADJECTIVE%":
            # "%ADJECTIVE%": the adjective variable inflected by the adj_NN* suffix rules,
            # placed by the language's adj_format ("adj $1$" in English).
            return self.loc.entries.get("adj_format", "adj $1$").replace("adj", "$adjective$", 1)
        if key == "%ADJ%":
            return key
        if key in self.loc.entries:
            template = self.loc.entries[key]
        elif not _KEY_LIKE.fullmatch(key) or (_PLAIN_WORD.fullmatch(key) and not has_variables):
            # Text the player typed ("Die Borg", "Vulkan") is sometimes stored without
            # literal = yes. Spaces or a plain capitalised word without underscores mark
            # it as typed text; real localisation keys carry underscores or are caps.
            template = key
        elif key.lstrip("-").isdigit():
            # sequence numbers arrive as bare numeric keys
            template = key
        elif "$" in key:
            # an inline template used as key, e.g. "$affix$$base$"
            template = key
        elif key in _BUILTIN_TEMPLATES:
            template = _BUILTIN_TEMPLATES[key]
        else:
            raise UnresolvedName(f"no localisation for name key {key!r}")
        if template == "%SEQ%":
            return "$fmt$"
        return template

    def _substitute(self, template: str, values: list[tuple[str, str]]) -> str:
        if template == "%ACRONYM%":
            base = dict(values).get("base", "")
            return "".join(word[0].upper() for word in base.split()) + base[-1:].upper()
        for var_key, value in values:
            if var_key == "num" and value.lstrip("-").isdigit():
                template = template.replace("$ORD$", _ordinal(int(value)))
                template = template.replace("$R$", _roman(int(value)))
            if var_key == "adjective":
                value = self._adjective(value)
            for left, right in (("<", ">"), ("[", "]"), ("$", "$"), ("%", "%")):
                template = template.replace(f"{left}{var_key}{right}", value, 1)
        template = self.loc._expand_references(template, depth=0)
        leftover = [
            m.group(0) for m in _VARIABLE.finditer(template) if m.group("key") not in ("ORD", "R")
        ]
        # Templates may carry optional slots ("$1$ $2$" with one value); the game drops them.
        for slot in leftover:
            if re.fullmatch(r"\$\d+\$", slot):
                template = template.replace(slot, "")
            else:
                raise UnresolvedName(f"unresolved variable {slot} in {template!r}")
        return template

    def _adjective(self, noun: str) -> str:
        for suffix in sorted(self.loc.adjective_suffixes, key=len, reverse=True):
            if noun.endswith(suffix):
                template = self.loc.adjective_suffixes[suffix]
                return template.replace("*", noun.removesuffix(suffix)).replace(" $1$", "")
        return noun


# Templates the game hard-codes rather than localising.
_BUILTIN_TEMPLATES = {
    "%LEADER_1%": "$1$ $2$",
    "%LEADER_2%": "$1$ $2$",
    "%SEQ%": "%SEQ%",
    "%ACRONYM%": "%ACRONYM%",
}


def _pick_variant(template: str, tags: set[str]) -> tuple[str, set[str]]:
    """Variants are separated by '|||' and checked right to left; each later variant
    lists required tags before a colon, and '&!' adds tags for nested names."""
    variants = template.split("|||")
    for index in reversed(range(len(variants))):
        variant = variants[index]
        added: set[str] = set()
        if "&!" in variant:
            variant, _, tag_list = variant.partition("&!")
            added = set(tag_list.split(","))
        required: set[str] = set()
        if index > 0 and ":" in variant:
            tag_list, _, variant = variant.partition(":")
            required = set(tag_list.split(","))
        if tags >= required:
            return variant, added
    return variants[0], set()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
