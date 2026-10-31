"""The admiralty:debrief skill is prose; these tests pin what it promises about tools and CLI."""

import asyncio
import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path

from test_setup import config_for

from admiralty.cli import main
from admiralty.debrief.epochs import check_epochs
from admiralty.mcp.server import build_server
from admiralty.workspace.setup import render_workspace_claude_md

SKILL = Path(__file__).parent.parent / "skills" / "debrief" / "SKILL.md"


def test_frontmatter_names_the_skill():
    text = SKILL.read_text()
    assert text.startswith("---\nname: debrief\n")
    assert re.search(r"^description: .{40,}", text, re.MULTILINE)


def test_every_tool_the_skill_names_is_served(tmp_path):
    text = SKILL.read_text()
    served = {tool.name for tool in asyncio.run(build_server(tmp_path).list_tools())}
    for tool in ("campaign_status", "retrospective", "timeline", "compare", "empire_overview"):
        assert f"`{tool}`" in text
        assert tool in served


def test_every_command_and_flag_the_skill_runs_exists():
    text = SKILL.read_text()
    assert "admiralty debrief check-epochs" in text
    helptext = _help(["debrief", "check-epochs", "--help"])
    for flag in ("--workspace", "--epochs", "--since", "--until"):
        assert flag in text
        assert flag in helptext


def test_the_retrospective_arguments_exist(tmp_path):
    tools = asyncio.run(build_server(tmp_path).list_tools())
    schema = next(t for t in tools if t.name == "retrospective").input_schema
    for argument in ("since", "until"):
        assert f"`{argument}`" in SKILL.read_text()
        assert argument in schema["properties"]


def test_the_epochs_example_has_the_checked_fields():
    block = re.search(r"```json\n(.*?)```", SKILL.read_text(), re.DOTALL).group(1)
    example = json.loads(re.sub(r"<[^>]*>", "x", block))
    assert all(set(epoch) == {"title", "from", "to", "anchor", "why"} for epoch in example)
    assert {"date", "event"} <= set(example[1]["anchor"])
    # the example is rejected for its invented dates, but not for a missing field
    verdict = check_epochs(example, [], "x", "x")
    assert not any("must be an object" in problem for problem in verdict["errors"])


def test_skill_keeps_the_hard_rules():
    text = SKILL.read_text()
    assert "Every number comes from a tool result" in text
    assert "Mark every Display Name in bold" in text
    assert "No benchmarks" in text
    assert "Fair Play" in text
    assert "You never write HTML" in text
    assert "Borders have anchors" in text
    assert "you add no rules" in text
    assert "`between`" in text


def test_the_skill_tells_the_reserve_in_months_and_the_systems_series():
    text = SKILL.read_text()
    assert "`reserve_months`" in text and "cushion, not an alarm" in text
    assert "`systems`" in text


def test_the_coaching_branch_asks_first_and_stays_inside_m8():
    text = SKILL.read_text()
    assert "ask the Player for **their own assessment**" in text
    assert "in one question" in text
    assert "wait for the answer" in text
    assert "you do not use\n`goals`" in text
    assert "no\nPlayer Model write" in text
    assert "nothing about Predictions" in text


def test_the_workspace_claude_md_routes_to_this_skill(tmp_path):
    for mode in ("consulting", "coaching"):
        text = render_workspace_claude_md(config_for(tmp_path, mode=mode))
        assert "admiralty:debrief" in text
    assert re.search(r"^name: debrief$", SKILL.read_text(), re.MULTILINE)


def _help(argv: list[str]) -> str:
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            main(argv)
    except SystemExit:
        pass
    return out.getvalue()
