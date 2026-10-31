"""The save service as a systemd user unit; the user manager is replaced by a recorder."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from admiralty.cli import main
from admiralty.workspace import watch_unit


class FakeSystemctl:
    def __init__(self, fail: str | None = None):
        self.calls: list[list[str]] = []
        self.fail = fail
        self.active = "inactive"

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        if args[0] == self.fail:
            return subprocess.CompletedProcess(args, 1, "", "Failed to connect to bus")
        if args[0] in ("enable", "restart"):
            self.active = "active"
        if args[0] == "disable":
            self.active = "inactive"
        out = {"is-active": self.active, "is-enabled": "enabled"}.get(args[0], "")
        return subprocess.CompletedProcess(args, 0 if out != "inactive" else 3, out + "\n", "")


def test_the_unit_starts_the_watcher_with_the_running_python(tmp_path):
    text = watch_unit.render_unit("/opt/uv env/bin/python", data_dir=tmp_path / "d e")
    assert "[Install]\nWantedBy=default.target" in text
    line = next(row for row in text.splitlines() if row.startswith("ExecStart="))
    assert line.startswith('ExecStart="/opt/uv env/bin/python" -m admiralty.cli watch')
    assert f'--data-dir "{(tmp_path / "d e").resolve()}"' in line
    assert "--save-root" not in line
    assert "Restart=on-failure" in text


def test_install_writes_the_unit_and_enables_it(tmp_path):
    systemctl = FakeSystemctl()
    unit_dir = tmp_path / "units"
    result = watch_unit.install(unit_dir, run=systemctl)
    path = unit_dir / "admiralty-watch.service"
    assert result == {"unit": str(path), "installed": True, "active": "active"}
    assert "admiralty.cli watch" in path.read_text()
    assert systemctl.calls[:2] == [
        ["daemon-reload"],
        ["enable", "--now", "admiralty-watch.service"],
    ]


def test_install_names_what_systemd_refused(tmp_path):
    with pytest.raises(watch_unit.UnitError) as refused:
        watch_unit.install(tmp_path, run=FakeSystemctl(fail="enable"))
    assert "enable --now admiralty-watch.service failed: Failed to connect to bus" in str(
        refused.value
    )


def test_uninstall_removes_the_unit_and_is_harmless_when_there_is_none(tmp_path):
    systemctl = FakeSystemctl()
    assert watch_unit.uninstall(tmp_path, run=systemctl)["removed"] is False
    assert systemctl.calls == []  # nothing to stop

    watch_unit.install(tmp_path, run=systemctl)
    systemctl.calls.clear()
    result = watch_unit.uninstall(tmp_path, run=systemctl)
    assert result["removed"] is True and not (tmp_path / "admiralty-watch.service").exists()
    assert systemctl.calls == [["disable", "--now", "admiralty-watch.service"], ["daemon-reload"]]


def test_status_names_the_unit_and_the_inbox(tmp_path):
    base = tmp_path / "data"
    inbox = base / "inbox" / "vulkan_1"
    inbox.mkdir(parents=True)
    (inbox / "2259.12.01.sav").write_bytes(b"12345")
    (inbox / "2259.12.02.autosave.sav").write_bytes(b"123")
    systemctl = FakeSystemctl()

    before = watch_unit.status(tmp_path / "units", base=base, run=systemctl)
    assert before["installed"] is False and before["active"] is None
    assert before["inbox"] == {
        "copies": 2,
        "bytes": 8,
        "folders": {"vulkan_1": {"copies": 2, "bytes": 8}},
    }
    assert systemctl.calls == []

    watch_unit.install(tmp_path / "units", run=systemctl)
    after = watch_unit.status(tmp_path / "units", base=base, run=systemctl)
    assert (after["installed"], after["enabled"], after["active"]) == (True, "enabled", "active")


def test_cli_install_status_uninstall_never_touch_the_real_user_manager(
    tmp_path, capsys, monkeypatch
):
    systemctl = FakeSystemctl()
    monkeypatch.setattr(watch_unit, "systemctl", systemctl)
    units = str(tmp_path / "units")
    data = str(tmp_path / "data")

    assert main(["watch", "install", "--unit-dir", units, "--data-dir", data]) == 0
    assert json.loads(capsys.readouterr().out)["active"] == "active"
    unit = (Path(units) / "admiralty-watch.service").read_text()
    assert f"--data-dir {Path(data).resolve()}" in unit

    assert main(["watch", "status", "--unit-dir", units, "--data-dir", data]) == 0
    assert json.loads(capsys.readouterr().out)["installed"] is True

    assert main(["watch", "uninstall", "--unit-dir", units]) == 0
    assert json.loads(capsys.readouterr().out)["removed"] is True


def test_cli_reports_a_refusal_on_stderr(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(watch_unit, "systemctl", FakeSystemctl(fail="daemon-reload"))
    assert main(["watch", "install", "--unit-dir", str(tmp_path)]) == 1
    assert (
        "admiralty watch install: systemctl --user daemon-reload failed" in capsys.readouterr().err
    )
