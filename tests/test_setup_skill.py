"""The admiralty:setup skill is prose; these tests pin what it promises about the CLI."""

import re
from pathlib import Path

from admiralty.cli import KNOWLEDGE, MODES

SKILL = Path(__file__).parent.parent / "skills" / "setup" / "SKILL.md"


def test_frontmatter_names_the_skill():
    text = SKILL.read_text()
    assert text.startswith("---\nname: setup\n")
    assert re.search(r"^description: .{40,}", text, re.MULTILINE)


def test_every_option_the_skill_passes_exists_in_the_cli():
    text = SKILL.read_text()
    for mode in MODES:
        assert mode in text
    for knowledge in KNOWLEDGE:
        assert knowledge in text
    for flag in ("--workspace", "--save-dir", "--empire", "--ally", "--rival", "--reset-archive"):
        assert flag in text


def test_skill_never_hands_out_yaml_writing():
    assert "never write or edit `campaign.yaml`" in SKILL.read_text()


def test_skill_bolds_display_names_only():
    text = SKILL.read_text()
    assert "Bold marks Display Names from the CLI output and nothing else" in text
    # the questions the skill dictates carry no bold terms (the check reads bold as a name)
    for term in ("Coaching", "Consulting", "Fair Play", "God Mode", "ally", "rival"):
        assert f"**{term}**" not in text


def test_skill_offers_the_save_service_and_passes_the_answer():
    text = SKILL.read_text()
    assert "admiralty setup autosave" in text
    assert "--save-service|--no-save-service" in text
    assert "never changes the\n   game's settings" in text


def test_skill_installs_the_unit_only_on_a_yes():
    text = " ".join(SKILL.read_text().split())
    assert "Only when the Player said yes in step 6: run `admiralty watch install`" in text
    assert "do not remove a unit that is already there" in text
