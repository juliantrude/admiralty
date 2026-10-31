"""The save service as a systemd user unit: `admiralty watch install | uninstall | status`.

`install` writes `~/.config/systemd/user/admiralty-watch.service` and enables it, so the watcher
(`admiralty watch`, workspace/watch.py) starts with the Player's session and is restarted when it
dies. `uninstall` disables it and removes the file. `status` says whether the unit exists and
runs and how much waits in the inbox. The unit starts the Python that runs this code
(`sys.executable -m admiralty.cli watch`), the same way the Briefing page starts its server.

The unit directory and the `systemctl` call are parameters, so tests never touch the Player's
home or the real user manager.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from admiralty.workspace import registry

UNIT_NAME = "admiralty-watch.service"
RESTART_SECONDS = 30

Systemctl = Callable[[Sequence[str]], subprocess.CompletedProcess]


class UnitError(Exception):
    """systemd refused or is not there; the message says what to do."""


def default_unit_dir() -> Path:
    return Path.home() / ".config/systemd/user"


def systemctl(args: Sequence[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["systemctl", "--user", *args], capture_output=True, text=True, timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise UnitError(f"systemctl --user is not available: {error}") from error


def _quote(word: str) -> str:
    """One word of an ExecStart line: systemd splits on spaces and reads % as a specifier."""
    word = word.replace("%", "%%").replace("$", "$$")
    if re.fullmatch(r"[\w@%:,./=+-]+", word):
        return word
    return '"' + word.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_unit(
    python: str = sys.executable,
    *,
    data_dir: Path | None = None,
    save_root: Path | None = None,
) -> str:
    command = [python, "-m", "admiralty.cli", "watch"]
    if save_root:
        command += ["--save-root", str(save_root.expanduser().resolve())]
    if data_dir:
        command += ["--data-dir", str(data_dir.expanduser().resolve())]
    return (
        "[Unit]\n"
        "Description=Admiralty save service (copies the Stellaris saves while the game runs)\n"
        "\n"
        "[Service]\n"
        f"ExecStart={' '.join(_quote(word) for word in command)}\n"
        "Restart=on-failure\n"
        f"RestartSec={RESTART_SECONDS}\n"
        "Nice=10\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def install(
    unit_dir: Path | None = None,
    *,
    run: Systemctl | None = None,
    data_dir: Path | None = None,
    save_root: Path | None = None,
) -> dict:
    """Write the unit and enable it now. Running it again rewrites the file and restarts."""
    run = run or systemctl
    path = (unit_dir or default_unit_dir()) / UNIT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_unit(data_dir=data_dir, save_root=save_root), encoding="utf-8")
    _must(run(["daemon-reload"]), "daemon-reload")
    _must(run(["enable", "--now", UNIT_NAME]), f"enable --now {UNIT_NAME}")
    _must(run(["restart", UNIT_NAME]), f"restart {UNIT_NAME}")  # pick up a rewritten unit
    return {"unit": str(path), "installed": True, "active": _state(run, "is-active")}


def uninstall(unit_dir: Path | None = None, *, run: Systemctl = systemctl) -> dict:
    run = run or systemctl
    path = (unit_dir or default_unit_dir()) / UNIT_NAME
    existed = path.exists()
    if existed:
        run(["disable", "--now", UNIT_NAME])  # a unit that is already gone is no error
        path.unlink()
        _must(run(["daemon-reload"]), "daemon-reload")
    return {"unit": str(path), "installed": False, "removed": existed}


def status(
    unit_dir: Path | None = None,
    *,
    base: Path | None = None,
    run: Systemctl | None = None,
) -> dict:
    run = run or systemctl
    path = (unit_dir or default_unit_dir()) / UNIT_NAME
    installed = path.exists()
    base = base or registry.data_dir()
    return {
        "unit": str(path),
        "installed": installed,
        "enabled": _state(run, "is-enabled") if installed else None,
        "active": _state(run, "is-active") if installed else None,
        "inbox": inbox_size(base),
        "workspaces": len(registry.load(base)),
    }


def inbox_size(base: Path) -> dict:
    """Saves that wait for a workspace: per Campaign folder the number of copies and their bytes."""
    folders = {}
    root = base / registry.INBOX_DIR
    if root.is_dir():
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            copies = [p for p in folder.glob("*.sav") if p.is_file()]
            if copies:
                folders[folder.name] = {
                    "copies": len(copies),
                    "bytes": sum(p.stat().st_size for p in copies),
                }
    return {
        "copies": sum(f["copies"] for f in folders.values()),
        "bytes": sum(f["bytes"] for f in folders.values()),
        "folders": folders,
    }


def _state(run: Systemctl, query: str) -> str:
    """`is-active` / `is-enabled` print the state (and exit non-zero for the bad ones)."""
    done = run([query, UNIT_NAME])
    return (done.stdout or "").strip() or "unknown"


def _must(done: subprocess.CompletedProcess, what: str) -> None:
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip()
        raise UnitError(f"systemctl --user {what} failed: {detail or f'exit {done.returncode}'}")
