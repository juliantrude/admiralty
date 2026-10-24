"""The game's own definitions (common/), parsed once per game version and cached."""

from __future__ import annotations

import hashlib
import pickle
import re
from functools import cached_property
from pathlib import Path
from typing import Any

from hlidskjalf.gamefiles.script import (
    ScriptError,
    _add,
    _parse_block,
    as_list,
    parse,
    parse_file,
    tokenize,
)

__all__ = ["GameData", "as_list"]

_CACHE_DIR = Path.home() / ".cache" / "hlidskjalf" / "gamefiles"


class GameData:
    """Lazy access to common/<category>/*.txt as one merged dict per category.

    Files load in name order and a later definition of the same key replaces an earlier
    one, which is how the game resolves duplicates for the object types we read.
    """

    def __init__(self, install_dir: Path, cache_dir: Path | None = _CACHE_DIR):
        self.install_dir = install_dir
        self.common = install_dir / "common"
        self.cache_dir = cache_dir
        self._categories: dict[str, dict[str, Any]] = {}
        self.errors: list[tuple[str, str]] = []

    @cached_property
    def version_stamp(self) -> str:
        """Identifies the installed game build, for cache invalidation."""
        manifest = self.install_dir / "checksum_manifest.txt"
        launcher = self.install_dir / "launcher-settings.json"
        digest = hashlib.sha1()
        for path in (manifest, launcher):
            if path.exists():
                digest.update(path.read_bytes())
        return digest.hexdigest()[:16]

    @cached_property
    def scripted_variables(self) -> dict[str, Any]:
        variables: dict[str, Any] = {}
        for path in sorted((self.common / "scripted_variables").glob("*.txt")):
            # parse_file collects @definitions into the scope it is given
            scope: dict[str, Any] = dict(variables)
            self._parse(path, scope)
            variables = scope
        return variables

    def category(self, name: str) -> dict[str, Any]:
        """All definitions under common/<name>/ (name may contain a slash, e.g.
        'governments/civics')."""
        if name not in self._categories:
            self._categories[name] = self._load_cached(name)
        return self._categories[name]

    def _load_cached(self, name: str) -> dict[str, Any]:
        cache = None
        if self.cache_dir is not None:
            cache = self.cache_dir / self.version_stamp / (name.replace("/", "__") + ".pickle")
            if cache.exists():
                return pickle.loads(cache.read_bytes())
        merged: dict[str, Any] = {}
        for path in sorted((self.common / name).glob("*.txt")):
            merged.update(self._parse(path, dict(self.scripted_variables)))
        if name != "inline_scripts":
            merged = self._expand_inline_scripts(merged, depth=0)
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(pickle.dumps(merged))
        return merged

    def _parse(self, path: Path, scope: dict[str, Any]) -> dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            block, _ = _parse_block(list(tokenize(text)), 0, scope, top=True)
            return block
        except ScriptError as error:
            self.errors.append((str(path.relative_to(self.install_dir)), str(error)))
            return {}

    def _expand_inline_scripts(self, value: Any, depth: int) -> Any:
        """Replace every inline_script = { script = path PARAM = x } by the script's
        content with $PARAM$ substituted, merged into the surrounding block."""
        if isinstance(value, list):
            return type(value)(self._expand_inline_scripts(v, depth) for v in value)
        if not isinstance(value, dict):
            return value
        out: dict[str, Any] = {}
        for key, child in value.items():
            if key != "inline_script" or depth > 8:
                _merge(out, key, self._expand_inline_scripts(child, depth))
                continue
            for call in as_list(child):
                expanded = self._inline_script(call)
                for inner_key, inner_value in expanded.items():
                    _merge(out, inner_key, self._expand_inline_scripts(inner_value, depth + 1))
        return out

    def _inline_script(self, call: Any) -> dict[str, Any]:
        if isinstance(call, str):
            script, params = call, {}
        elif isinstance(call, dict) and "script" in call:
            script = call["script"]
            params = {k: v for k, v in call.items() if k != "script"}
        else:
            return {}
        path = self.common / "inline_scripts" / f"{script}.txt"
        if not path.exists():
            self.errors.append((str(path), "inline script not found"))
            return {}
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        text = _apply_inline_params(text, {k: _param_text(v) for k, v in params.items()})
        try:
            return parse(text, self.scripted_variables)
        except ScriptError as error:
            self.errors.append((str(path), str(error)))
            return {}

    def defines(self) -> dict[str, Any]:
        """NDefines flattened: {'NGameplay': {...}, 'NEconomy': {...}, ...}."""
        merged: dict[str, Any] = {}
        for path in sorted((self.common / "defines").glob("*.txt")):
            for group, values in parse_file(path).items():
                if isinstance(values, dict):
                    merged.setdefault(group, {}).update(values)
        return merged


def _merge(block: dict[str, Any], key: str, value: Any) -> None:
    _add(block, key, value)


def _param_text(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


_CONDITIONAL = re.compile(r"\[\[(!?)(\w+)\]")


def _apply_inline_params(text: str, params: dict[str, str]) -> str:
    """$PARAM$ and $PARAM|default$ substitution plus [[PARAM] ... ] / [[!PARAM] ... ]
    conditional sections, as documented for inline scripts."""
    out: list[str] = []
    pos = 0
    while True:
        match = _CONDITIONAL.search(text, pos)
        if not match:
            out.append(text[pos:])
            break
        out.append(text[pos : match.start()])
        # find the closing bracket of this section, allowing nested sections
        depth, index = 1, match.end()
        while index < len(text) and depth:
            if text.startswith("[[", index):
                depth += 1
                index += 2
                continue
            if text[index] == "]":
                depth -= 1
            index += 1
        body = text[match.end() : index - 1]
        negate, name = match.group(1) == "!", match.group(2)
        if (name in params) != negate:
            out.append(_apply_inline_params(body, params))
        pos = index
    text = "".join(out)

    def substitute(found: re.Match[str]) -> str:
        name, _, default = found.group(1).partition("|")
        return params.get(name, default if default else found.group(0))

    return re.sub(r"\$([A-Za-z0-9_|.\-]+)\$", substitute, text)
