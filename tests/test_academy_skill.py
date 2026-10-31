"""The admiralty:academy skill is prose; these tests pin what it promises about tools, outcomes and rules."""

import asyncio
import inspect
import re
from pathlib import Path

from test_setup import config_for

from admiralty.academy import drill, ladder, tools, topics
from admiralty.mcp.server import build_server
from admiralty.player import evidence
from admiralty.player.mastery import OUTCOMES
from admiralty.workspace.setup import render_workspace_claude_md

ROOT = Path(__file__).parent.parent
SKILL = ROOT / "skills" / "academy" / "SKILL.md"
OPS = ROOT / "skills" / "ops" / "SKILL.md"

ACADEMY_TOOLS = (
    "academy_open",
    "academy_attempt",
    "academy_next",
    "academy_escape",
    "academy_close",
    "prediction_add",
    "prediction_check",
    "rendezvous_set",
    "player_model",
)


def flat(text: str) -> str:
    return " ".join(text.replace("**", "").split())


def test_frontmatter_names_the_skill():
    text = SKILL.read_text()
    assert text.startswith("---\nname: academy\n")
    assert re.search(r"^description: .{40,}", text, re.MULTILINE)


def test_every_tool_the_skill_names_is_served(tmp_path):
    text = SKILL.read_text()
    served = {tool.name for tool in asyncio.run(build_server(tmp_path).list_tools())}
    for tool in (
        *ACADEMY_TOOLS,
        "campaign_status",
        "empire_overview",
        "economy",
        "progression",
        "military",
        "planets",
        "timeline",
        "compare",
    ):
        assert f"`{tool}`" in text
        assert tool in served


def test_the_commands_the_skill_names_exist(tmp_path):
    assert "admiralty academy" in SKILL.read_text()
    from admiralty.cli import main

    for name in ("open", "attempt", "next", "escape", "close", "prediction-add"):
        try:
            main(["academy", name, "--help"])
        except SystemExit as stop:
            assert stop.code == 0


def test_every_outcome_the_skill_names_is_one_the_tool_accepts():
    text = SKILL.read_text()
    step = re.search(r"3\. \*\*Report.*?\n4\. ", text, re.DOTALL).group(0)
    named = set(re.findall(r"`(\w+)`:", step))
    assert named == set(OUTCOMES)
    for outcome in OUTCOMES:
        assert f"`{outcome}`" in text


def test_the_support_shape_is_the_one_the_tool_checks():
    text = SKILL.read_text()
    assert '{"path": ..., "op": ..., "value": ...}' in text
    source = inspect.getsource(tools.check_support)
    assert 'set(support) != {"path", "op", "value"}' in source


def test_the_ladder_levels_are_the_ones_the_code_has():
    text = flat(SKILL.read_text())
    for name in ladder.NAMES.values():
        assert f"`{name}`" in text
    assert "two in a Crisis" in text
    assert "Socratic" in text
    for what in ladder.NAMED:
        assert f"`{what}`" in text


def test_the_result_keys_the_skill_reads_are_in_the_code():
    text = SKILL.read_text()
    source = "".join(inspect.getsource(m) for m in (tools, drill, topics, evidence))
    for key in (
        "needs_goals",
        "newer_save",
        "changes",
        "ask_once",
        "ask_where",
        "announce",
        "announced",
        "happened",
        "answer",
        "asks_for",
        "ladder_name",
        "pointers",
        "where",
        "open_question",
        "waiting",
        "proposal",
        "crisis",
        "concepts",
    ):
        assert f"`{key}`" in text, key
        assert f'"{key}"' in source or f"'{key}'" in source or f"{key}=" in source, key


def test_the_flow_keeps_the_agreed_rules():
    text = flat(SKILL.read_text())
    assert "On every message of the Player, first call `academy_open`" in text
    assert "one entry question" in text
    assert "One question at a time" in text
    assert "without saying what they are" in text
    assert "Below a Crisis there is no warning" in text
    assert "what they expect to happen in two years" in text
    assert "In a Crisis" in text and "in question mode" in text
    assert "Do not state a Key Action before the Player's own attempt" in text
    assert "full explanation" in text and "Ladder level 4" in text
    assert "Situation" in text and "Escape Hatch" in text
    assert "each counts as an Escape Hatch" in text
    assert "a summary of two or three sentences" in text
    assert "at most five in-game years" in text
    assert "`before`" in text and "`at`" in text and "`after`" in text
    assert "admiralty:debrief" in text
    assert "Never confirm or refute a Prediction yourself" in text


def test_the_tone_is_set_down():
    text = flat(SKILL.read_text())
    assert 'for a German Player that is "du"' in text
    assert "short sentences" in text and "light fleet tone" in text
    assert "no role play" in text and "never condescending" in text
    assert "Neues Save, Juni 2247" in text
    assert "Wie schätzt du die Lage ein, woran liegt das?" in text


def test_the_hard_rules_are_present():
    text = flat(SKILL.read_text())
    assert "Every number comes from a tool result" in text
    assert "Mark every Display Name in bold" in text
    assert "The Player Model changes only through the tools" in text
    assert "player-model/" in text
    assert "Fair Play" in text
    assert "knowledge: fair_play" in text and "knowledge: god_mode" in text
    assert "point only at what the Tracked Empire can see itself" in text
    assert "No benchmarks" in text
    assert "No tool or command names" in text
    assert "Never stop for good on a stale save" in text


def test_nothing_tells_the_model_to_show_the_solution_graph():
    text = flat(SKILL.read_text())
    assert "never show the Solution Graph" in text
    assert "Never show a graph" in text
    positive = re.sub(r"(?i)never show (the solution graph|a graph)", "", text)
    assert not re.search(r"(?i)show (the |a )?(solution )?graph", positive)
    for forbidden in ("expand_graph", "briefing compose", "check-solution", "overlay"):
        assert forbidden not in text


def test_the_title_paragraph_is_the_one_ops_has():
    ops = flat(OPS.read_text())
    text = flat(SKILL.read_text())
    for sentence in (
        "A Goal is the wanted state as a phrase of at most five words with no request",
        'an amount with its direction first ("More alloy income")',
        'A Cause is a short state ("Few staffed Metallurgist jobs")',
        'a Remedy an instruction of at most five words ("Open more job slots")',
        'an Obstacle says what is missing ("No free building slot")',
        "with no figures",
    ):
        assert sentence in ops
        assert sentence in text


def test_the_workspace_claude_md_routes_to_this_skill(tmp_path):
    text = render_workspace_claude_md(config_for(tmp_path, mode="coaching"))
    assert "admiralty:academy" in text and "admiralty:ops" not in text
    assert "may not be installed" not in text
    assert re.search(r"^name: academy$", SKILL.read_text(), re.MULTILINE)
