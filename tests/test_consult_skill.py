"""The hlidskjalf:consult skill is prose; these tests pin what it promises about tools and CLI."""

import asyncio
import re
from pathlib import Path

from test_setup import config_for

from hlidskjalf.cli import main
from hlidskjalf.graph.solution import _OVERLAY_KEYS
from hlidskjalf.mcp.server import build_server
from hlidskjalf.workspace.setup import render_workspace_claude_md

SKILL = Path(__file__).parent.parent / "skills" / "huginn-consult" / "SKILL.md"


def test_frontmatter_names_the_skill():
    text = SKILL.read_text()
    assert text.startswith("---\nname: consult\n")
    assert re.search(r"^description: .{40,}", text, re.MULTILINE)


def test_every_tool_the_skill_names_is_served(tmp_path):
    text = SKILL.read_text()
    served = {tool.name for tool in asyncio.run(build_server(tmp_path).list_tools())}
    for tool in (
        "campaign_status",
        "empire_overview",
        "economy",
        "progression",
        "military",
        "expand_graph",
    ):
        assert f"`{tool}`" in text
        assert tool in served


def test_every_command_and_flag_the_skill_runs_exists():
    text = SKILL.read_text()
    for command in ("briefing compose", "graph check-solution"):
        assert f"hlidskjalf {command}" in text
    for flag in ("--expansion-id", "--workspace", "--out"):
        assert flag in text
        assert _cli_accepts(flag)


def test_the_overlay_example_uses_only_known_fields():
    block = re.search(r"```json\n(.*?)```", SKILL.read_text(), re.DOTALL).group(1)
    fields = set(re.findall(r'^  "(\w+)":', block, re.MULTILINE))
    assert fields == _OVERLAY_KEYS


def test_skill_keeps_the_hard_rules():
    text = SKILL.read_text()
    assert "unity-vs-next-tradition" in text and "traditions.next_cost" in text
    assert "does not recommend spending it elsewhere" in text
    assert "You never write HTML" in text
    assert "No benchmarks" in text
    assert "Fair Play" in text
    assert "Every number comes from a tool result" in text
    assert "Three Goals in total" in text
    assert "Mark every Display Name in bold" in text


def test_the_workspace_claude_md_routes_to_this_skill(tmp_path):
    text = render_workspace_claude_md(config_for(tmp_path, mode="consulting"))
    assert "hlidskjalf:consult" in text
    assert re.search(r"^name: consult$", SKILL.read_text(), re.MULTILINE)


def _cli_accepts(flag: str) -> bool:
    import io
    from contextlib import redirect_stdout

    out = io.StringIO()
    try:
        with redirect_stdout(out):
            main(["briefing", "compose", "--help"])
    except SystemExit:
        pass
    return flag in out.getvalue()
