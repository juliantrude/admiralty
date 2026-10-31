"""The autosave interval the Player has set, read from settings.txt, and the hint about it."""

import pytest
import yaml
from test_setup import run

from admiralty.workspace.autosave import AUTOSAVE_OPTIONS, autosave_hint, read_autosave
from admiralty.workspace.config import CONFIG_FILE, CampaignConfig, write_config


def settings(tmp_path, text):
    (tmp_path / "settings.txt").write_text(text, encoding="utf-8")
    return tmp_path


def test_options_are_the_game_order():
    assert [name for name, _ in AUTOSAVE_OPTIONS] == [
        "Never",
        "Daily",
        "Monthly",
        "Quarterly",
        "Semiannually",
        "Annually",
    ]


@pytest.mark.parametrize(
    ("value", "name", "recommend"),
    [
        (0, "Never", True),
        (1, "Daily", False),
        (2, "Monthly", False),
        (3, "Quarterly", False),
        (4, "Semiannually", True),
        (5, "Annually", True),
    ],
)
def test_each_value_reads_as_the_game_names_it(tmp_path, value, name, recommend):
    found = read_autosave(settings(tmp_path, f'name="X"\nautosave={value}\ntutorial=2\n'))
    assert (found["setting"], found["recommend"]) == (name, recommend)


@pytest.mark.parametrize(
    "text", ["", "autosave=\n", "autosave=9\n", "tautosave=3\n", "autosave=x\n"]
)
def test_a_missing_or_odd_value_gives_no_recommendation(tmp_path, text):
    found = read_autosave(settings(tmp_path, text))
    assert found == {"setting": None, "months": None, "recommend": False}


def test_no_settings_file_is_no_error(tmp_path):
    assert read_autosave(tmp_path)["setting"] is None
    assert "could not be read" in autosave_hint(tmp_path)["hint"]


def test_hint_recommends_quarterly_only_when_rarer(tmp_path):
    rare = autosave_hint(settings(tmp_path, "autosave=4\n"))
    assert rare["recommended"] == "Quarterly" and "does not change it" in rare["hint"]
    often = autosave_hint(settings(tmp_path, "autosave=2\n"))
    assert often["recommended"] is None and "Monthly" in often["hint"]


def test_the_settings_file_is_never_touched(tmp_path):
    folder = settings(tmp_path, "autosave=4\n")
    before = (folder / "settings.txt").read_bytes()
    autosave_hint(folder)
    assert (folder / "settings.txt").read_bytes() == before


def test_cli_prints_the_hint(tmp_path, capsys):
    folder = settings(tmp_path, "autosave=0\n")
    code, result, _ = run(capsys, "autosave", "--user-dir", folder)
    assert code == 0
    assert result["setting"] == "Never" and result["recommended"] == "Quarterly"


# --- the answer to the offer of the save service ------------------------------------------


def test_the_answer_is_stored_and_kept_when_not_given_again(tmp_path):
    workspace = tmp_path / "ws"
    base = {"save_dir": str(tmp_path), "empire": "Plexxi"}
    assert write_config(workspace, **base).save_service is False
    assert write_config(workspace, save_service=True).save_service is True
    assert write_config(workspace, **base).save_service is True
    assert yaml.safe_load((workspace / CONFIG_FILE).read_text())["save_service"] is True
    assert CampaignConfig.load(workspace).save_service is True


def test_setup_write_passes_the_answer(vulkan_folder, tmp_path, capsys):
    workspace = tmp_path / "ws"
    args = ["write", "--workspace", workspace, "--save-dir", vulkan_folder, "--empire", "Plexxi"]
    code, result, _ = run(capsys, *args)
    assert code == 0 and result["save_service"] is False
    code, result, _ = run(capsys, *args, "--save-service")
    assert code == 0 and result["save_service"] is True
    code, result, _ = run(capsys, *args)  # no answer given again: the earlier one stays
    assert result["save_service"] is True
    code, result, _ = run(capsys, *args, "--no-save-service")
    assert result["save_service"] is False
