"""Campaign Setup: finding Campaigns, the `admiralty setup` CLI, the generated CLAUDE.md."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest
import yaml
from conftest import MID, VULKAN, reference_save

from admiralty.cli import main
from admiralty.workspace.archive import EXTRACT_SUFFIX
from admiralty.workspace.config import CONFIG_FILE, CampaignConfig, Player
from admiralty.workspace.setup import (
    WORKSPACE_CLAUDE_MD,
    SetupRefused,
    describe_save,
    list_campaigns,
    render_workspace_claude_md,
    write_setup,
)


@pytest.fixture(autouse=True)
def no_env_overrides(monkeypatch):
    monkeypatch.delenv("ADMIRALTY_SAVE_DIR", raising=False)
    monkeypatch.delenv("ADMIRALTY_EMPIRE", raising=False)


def fake_save(path: Path, name="Test Campaign", date="2259.12.29", mtime=None) -> Path:
    """A zip with only a meta file: enough for everything that reads no gamestate."""
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = f'version="Cygnus v4.5.2"\ndate="{date}"\nname="mp_{name}"\n'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("meta", meta)
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


@pytest.fixture
def vulkan_folder(tmp_path, mid_save) -> Path:
    """A copy of the reference Campaign folder (symlink) under tmp, as the game lays it out."""
    folder = tmp_path / "save games" / "mpvulkan_1"
    folder.mkdir(parents=True)
    (folder / mid_save.name).symlink_to(mid_save)
    return folder


def run(capsys, *argv) -> tuple[int, dict | None, str]:
    code = main(["setup", *map(str, argv)])
    captured = capsys.readouterr()
    return code, json.loads(captured.out) if captured.out.strip() else None, captured.err


# --- finding Campaigns (no reference save needed) ---------------------------------------


def test_campaigns_lists_folders_with_saves_newest_first(tmp_path, capsys):
    root = tmp_path / "save games"
    fake_save(root / "mpold_1" / "2230.01.01.sav", "Old", "2230.01.05", mtime=1_000_000)
    fake_save(root / "mpnew_2" / "a.sav", "New", "2250.02.02", mtime=1_900_000_000)
    fake_save(root / "mpnew_2" / "b.sav", "New", "2250.03.03", mtime=2_000_000_000)
    (root / "empty_3").mkdir()
    (root / "stray.txt").write_text("not a campaign")

    code, result, _ = run(capsys, "campaigns", "--save-root", root)

    assert code == 0 and result["save_root"] == str(root)
    assert [c["campaign"] for c in result["campaigns"]] == ["New", "Old"]
    new = result["campaigns"][0]
    assert (new["saves"], new["newest_save"], new["newest_date"]) == (2, "b.sav", "2250.03.03")
    assert new["folder"] == str(root / "mpnew_2") and new["game_version"] == "4.5.2"


def test_a_broken_newest_save_still_lists_the_campaign(tmp_path):
    root = tmp_path / "save games"
    broken = root / "mpbroken_1" / "2250.01.01.sav"
    broken.parent.mkdir(parents=True)
    broken.write_bytes(b"half written")

    (entry,) = list_campaigns(root)

    assert entry["campaign"] == "mpbroken_1" and entry["newest_date"] is None


def test_campaigns_on_a_missing_root_is_empty(tmp_path):
    assert list_campaigns(tmp_path / "nowhere") == []


# --- refusals before any extraction ---------------------------------------------------------


def test_write_refuses_a_save_dir_that_does_not_exist(tmp_path, capsys):
    code, result, err = run(
        capsys,
        "write",
        "--workspace",
        tmp_path / "ws",
        "--save-dir",
        tmp_path / "x",
        "--empire",
        "A",
    )

    assert code == 1 and result is None and "setup campaigns" in err
    assert not (tmp_path / "ws").exists()


def test_players_of_a_folder_without_saves_is_an_error(tmp_path, capsys):
    (tmp_path / "empty").mkdir()

    code, _, err = run(capsys, "players", tmp_path / "empty")

    assert code == 1 and "no saves" in err


def test_check_on_a_missing_setup_reports_it(tmp_path, capsys):
    code, result, _ = run(capsys, "check", "--workspace", tmp_path)

    assert code == 1 and result["ok"] is False
    assert any("Campaign Setup" in p for p in result["problems"])


# --- CLAUDE.md template ------------------------------------------------------------------------


def config_for(tmp_path, **fields) -> CampaignConfig:
    from admiralty.workspace.config import write_config

    folder = fake_save(tmp_path / "saves-in" / "x.sav").parent
    return write_config(
        tmp_path / "ws", save_dir=folder, empire="Plexxi", campaign="Test Campaign", **fields
    )


def test_claude_md_routes_consulting_to_consult(tmp_path):
    text = render_workspace_claude_md(config_for(tmp_path, mode="consulting"))

    assert "admiralty:ops" in text and "admiralty:academy" not in text
    assert "admiralty:debrief" in text and "admiralty:setup" in text
    assert "Test Campaign" in text and "Plexxi" in text and "Fair Play" in text


def test_claude_md_routes_coaching_to_coach_and_lists_players(tmp_path):
    config = config_for(
        tmp_path,
        mode="coaching",
        knowledge="god_mode",
        players=[Player("Anna", "ally"), Player("Ben", "rival")],
    )

    text = render_workspace_claude_md(config)

    assert "admiralty:academy" in text and "admiralty:ops" not in text
    assert "God Mode" in text and "Anna (ally)" in text and "Ben (rival)" in text


# --- against a reference save (skips without) ---------------------------------------------


def other_players(info):
    return [p["name"] for p in info["players"] if p["name"] != "Plexxi"]


def test_players_lists_empires_with_display_names(vulkan_folder, capsys):
    code, result, _ = run(capsys, "players", vulkan_folder)

    assert code == 0 and result["save_file"] == MID
    assert result["game_version"] == "4.5.2"
    plexxi = next(p for p in result["players"] if p["name"] == "Plexxi")
    assert plexxi["empire"] and "." not in plexxi["empire"]  # a Display Name, not a loc key
    assert isinstance(plexxi["country_id"], int)


def test_write_creates_a_valid_workspace_and_check_is_clean(vulkan_folder, tmp_path, capsys):
    ws = tmp_path / "ws"
    others = other_players(describe_save(vulkan_folder))
    code, result, err = run(
        capsys,
        "write",
        "--workspace", ws,
        "--save-dir", vulkan_folder,
        "--empire", "plexxi",
        "--mode", "coaching",
        "--knowledge", "god_mode",
        "--ally", others[0],
        "--no-backup",
    )  # fmt: skip

    assert code == 0, err
    assert result["tracked_empire"]["player"] == "Plexxi"  # normalised from "plexxi"
    saved = yaml.safe_load((ws / CONFIG_FILE).read_text())
    assert (saved["empire"], saved["mode"], saved["knowledge"]) == (
        "Plexxi",
        "coaching",
        "god_mode",
    )
    assert saved["backup_saves"] is False and saved["version"] == 1
    assert saved["players"] == [{"name": others[0], "relation": "ally"}]
    assert "admiralty:academy" in (ws / WORKSPACE_CLAUDE_MD).read_text()
    for name in ("archive", "saves", "predictions", ".admiralty"):
        assert (ws / name).is_dir()

    code, check, _ = run(capsys, "check", "--workspace", ws)
    assert code == 0 and check == {"ok": True, "problems": []}


def test_write_is_idempotent_and_keeps_archive_saves_and_hand_edits(vulkan_folder, tmp_path):
    ws = tmp_path / "ws"
    write_setup(ws, vulkan_folder, "Plexxi")
    (ws / "archive" / f"2259.12.29{EXTRACT_SUFFIX}").write_bytes(b"kept")
    (ws / "saves" / "2259.12.29.sav").write_bytes(b"kept")
    text = (ws / CONFIG_FILE).read_text()
    (ws / CONFIG_FILE).write_text(text + "my_note: stays\n")

    other = other_players(describe_save(vulkan_folder))[0]

    write_setup(ws, vulkan_folder, "Plexxi", mode="coaching", rivals=(other,))

    saved = yaml.safe_load((ws / CONFIG_FILE).read_text())
    assert saved["mode"] == "coaching" and saved["my_note"] == "stays"
    assert saved["players"] == [{"name": other, "relation": "rival"}]
    assert (ws / "archive" / f"2259.12.29{EXTRACT_SUFFIX}").read_bytes() == b"kept"
    assert (ws / "saves" / "2259.12.29.sav").read_bytes() == b"kept"
    assert "admiralty:academy" in (ws / WORKSPACE_CLAUDE_MD).read_text()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"empire": "No Such Empire"}, "No player or empire 'No Such Empire'"),
        ({"empire": "Plexxi", "allies": ("Nobody",)}, "No player 'Nobody'"),
        ({"empire": "Plexxi", "rivals": ("Nobody",)}, "No player 'Nobody'"),
        ({"empire": "Plexxi", "allies": ("Plexxi",)}, "is the Tracked Empire"),
    ],
)
def test_write_rejects_unknown_choices_and_writes_nothing(vulkan_folder, tmp_path, kwargs, message):
    ws = tmp_path / "ws"

    with pytest.raises(SetupRefused, match=message):
        write_setup(ws, vulkan_folder, **kwargs)

    assert not ws.exists()


def test_write_rejects_the_same_player_as_ally_and_rival(vulkan_folder, tmp_path):
    other = other_players(describe_save(vulkan_folder))[0]

    with pytest.raises(SetupRefused, match="ally and rival"):
        write_setup(tmp_path / "ws", vulkan_folder, "Plexxi", allies=(other,), rivals=(other,))


def test_changing_the_tracked_empire_needs_reset_archive_and_never_deletes(vulkan_folder, tmp_path):
    ws = tmp_path / "ws"
    write_setup(ws, vulkan_folder, "Plexxi")
    entry = ws / "archive" / f"2259.12.29{EXTRACT_SUFFIX}"
    entry.write_bytes(b"old empire")
    other = other_players(describe_save(vulkan_folder))[0]

    with pytest.raises(SetupRefused, match="--reset-archive"):
        write_setup(ws, vulkan_folder, other)
    assert entry.read_bytes() == b"old empire"
    assert yaml.safe_load((ws / CONFIG_FILE).read_text())["empire"] == "Plexxi"

    result = write_setup(ws, vulkan_folder, other, reset_archive=True)

    assert Path(result["archive_moved_to"]) == ws / "archive.1"
    assert (ws / "archive.1" / entry.name).read_bytes() == b"old empire"
    assert list((ws / "archive").iterdir()) == []


def test_check_finds_a_tracked_empire_that_left_the_save(vulkan_folder, tmp_path, capsys):
    ws = tmp_path / "ws"
    write_setup(ws, vulkan_folder, "Plexxi")
    (ws / CONFIG_FILE).write_text(
        (ws / CONFIG_FILE).read_text().replace("empire: Plexxi", "empire: Ghost")
    )

    code, result, _ = run(capsys, "check", "--workspace", ws)

    assert code == 1 and any("Ghost" in p for p in result["problems"])


def test_reference_campaign_is_found_by_campaigns(vulkan_folder, capsys):
    code, result, _ = run(capsys, "campaigns", "--save-root", vulkan_folder.parent)

    assert code == 0 and result["campaigns"][0]["campaign"]
    assert result["campaigns"][0]["newest_save"] == MID
    assert reference_save(VULKAN, MID)  # skip marker kept explicit
