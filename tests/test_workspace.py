"""Campaign Workspace: campaign.yaml round-trips and validation, directory layout."""

from __future__ import annotations

import pytest
import yaml

from hlidskjalf.workspace.config import (
    CONFIG_FILE,
    CampaignConfig,
    Player,
    SetupInvalid,
    SetupMissing,
    write_config,
)
from hlidskjalf.workspace.layout import (
    DIRECTORIES,
    NotAWorkspace,
    create_workspace,
    validate_workspace,
)


@pytest.fixture(autouse=True)
def no_env_overrides(monkeypatch):
    monkeypatch.delenv("HLIDSKJALF_SAVE_DIR", raising=False)
    monkeypatch.delenv("HLIDSKJALF_EMPIRE", raising=False)


def saves(tmp_path):
    folder = tmp_path / "save games" / "campaign"
    folder.mkdir(parents=True)
    (folder / "2259.12.25.sav").write_bytes(b"")
    return folder


# --- config ------------------------------------------------------------------------------


def test_write_then_load_round_trip(tmp_path):
    folder = saves(tmp_path)
    ws = tmp_path / "ws"
    write_config(
        ws,
        save_dir=folder,
        empire="Plexxi",
        mode="coaching",
        knowledge="god_mode",
        backup_saves=False,
        players=[Player("Anna", "ally"), {"name": "Ben", "relation": "rival"}],
    )
    config = CampaignConfig.load(ws)
    assert config.save_dir == folder
    assert (config.empire, config.mode, config.god_mode) == ("Plexxi", "coaching", True)
    assert config.backup_saves is False
    assert config.players == (Player("Anna", "ally"), Player("Ben", "rival"))
    assert yaml.safe_load((ws / CONFIG_FILE).read_text())["version"] == 1


def test_defaults_when_only_the_required_keys_are_set(tmp_path):
    (tmp_path / CONFIG_FILE).write_text("save_dir: /x\nempire: 3\n")
    config = CampaignConfig.load(tmp_path)
    assert (config.mode, config.knowledge) == ("consulting", "fair_play")
    assert config.backup_saves is True and config.players == ()


def test_rewrite_keeps_hand_added_keys_and_removes_none_fields(tmp_path):
    ws = tmp_path
    (ws / CONFIG_FILE).write_text("save_dir: /x\nempire: Plexxi\nnote: hand written\n")
    write_config(ws, mode="coaching", players=[Player("Anna", "ally")])
    write_config(ws, players=None)
    data = yaml.safe_load((ws / CONFIG_FILE).read_text())
    assert data["note"] == "hand written" and data["mode"] == "coaching"
    assert "players" not in data


@pytest.mark.parametrize(
    "fields, message",
    [
        ({"mode": "autopilot"}, "mode must be"),
        ({"knowledge": "cheating"}, "knowledge must be"),
        ({"backup_saves": "yes"}, "backup_saves must be"),
        ({"players": [{"name": "Anna", "relation": "friend"}]}, "ally or rival"),
        ({"players": [{"relation": "ally"}]}, "needs a name"),
        ({"players": [Player("A", "ally"), Player("A", "rival")]}, "listed twice"),
    ],
)
def test_invalid_values_are_rejected_and_leave_the_file_alone(tmp_path, fields, message):
    write_config(tmp_path, save_dir="/x", empire="Plexxi")
    before = (tmp_path / CONFIG_FILE).read_text()
    with pytest.raises(SetupInvalid, match=message):
        write_config(tmp_path, **fields)
    assert (tmp_path / CONFIG_FILE).read_text() == before
    assert [p.name for p in tmp_path.iterdir()] == [CONFIG_FILE]  # no temp file left behind


def test_hand_written_invalid_mode_fails_on_load(tmp_path):
    (tmp_path / CONFIG_FILE).write_text("save_dir: /x\nempire: P\nmode: autopilot\n")
    with pytest.raises(SetupMissing, match="mode must be"):  # SetupInvalid is a SetupMissing
        CampaignConfig.load(tmp_path)


def test_env_overrides_still_win(tmp_path, monkeypatch):
    write_config(tmp_path, save_dir="/x", empire="Plexxi")
    monkeypatch.setenv("HLIDSKJALF_SAVE_DIR", "/elsewhere")
    monkeypatch.setenv("HLIDSKJALF_EMPIRE", "Other")
    config = CampaignConfig.load(tmp_path)
    assert (str(config.save_dir), config.empire) == ("/elsewhere", "Other")


def test_env_alone_works_without_a_yaml_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HLIDSKJALF_SAVE_DIR", "/elsewhere")
    monkeypatch.setenv("HLIDSKJALF_EMPIRE", "Other")
    assert CampaignConfig.load(tmp_path).empire == "Other"


# --- layout ------------------------------------------------------------------------------


def test_create_in_new_and_empty_directory_and_again(tmp_path):
    ws = create_workspace(tmp_path / "new" / "ws")
    assert all((ws / name).is_dir() for name in DIRECTORIES)
    empty = tmp_path / "empty"
    empty.mkdir()
    create_workspace(empty)
    assert create_workspace(ws) == ws  # idempotent


def test_create_refuses_a_foreign_directory(tmp_path):
    (tmp_path / "thesis.docx").write_bytes(b"")
    with pytest.raises(NotAWorkspace, match="not empty"):
        create_workspace(tmp_path)
    assert not (tmp_path / "archive").exists()


def test_create_accepts_a_directory_that_only_has_a_setup(tmp_path):
    write_config(tmp_path, save_dir="/x", empire="P")
    create_workspace(tmp_path)
    assert (tmp_path / "archive").is_dir()


def test_validate_a_ready_workspace_is_clean(tmp_path):
    ws = create_workspace(tmp_path / "ws")
    write_config(ws, save_dir=saves(tmp_path), empire="Plexxi")
    assert validate_workspace(ws) == []


def test_validate_reports_each_problem(tmp_path):
    assert "does not exist" in validate_workspace(tmp_path / "nope")[0]
    ws = tmp_path / "ws"
    ws.mkdir()
    assert "hlidskjalf:setup" in validate_workspace(ws)[0]  # no campaign.yaml
    write_config(ws, save_dir=tmp_path / "gone", empire="Plexxi")
    problems = validate_workspace(ws)
    assert any("archive/ is missing" in p for p in problems)
    assert any("save_dir" in p and "does not exist" in p for p in problems)
    (tmp_path / "gone").mkdir()
    assert any("holds no saves" in p for p in validate_workspace(ws))


def test_validate_checks_empire_and_players_against_the_save_header(tmp_path):
    ws = create_workspace(tmp_path / "ws")
    write_config(
        ws,
        save_dir=saves(tmp_path),
        empire="Plexxi",
        players=[Player("Anna", "ally"), Player("Zed", "rival")],
    )
    header_players = [
        {"name": "Plexxi", "country_id": 0, "empire": "Konföderation von Vulkan"},
        {"name": "Anna", "country_id": 1, "empire": "Other Empire"},
    ]
    assert validate_workspace(ws, header_players) == ["player 'Zed' is not in the newest save"]
    write_config(ws, empire="Nobody", players=None)
    assert "empire 'Nobody'" in validate_workspace(ws, header_players)[0]
    write_config(ws, empire="Konföderation von Vulkan")  # empire Display Name is accepted
    assert validate_workspace(ws, header_players) == []
