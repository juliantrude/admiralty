"""The admiralty:ops skill is prose; these tests pin what it promises about tools and CLI."""

import asyncio
import re
from pathlib import Path

from test_setup import config_for

from admiralty.cli import main
from admiralty.graph.solution import _OVERLAY_KEYS
from admiralty.mcp.server import build_server
from admiralty.workspace.setup import render_workspace_claude_md

SKILL = Path(__file__).parent.parent / "skills" / "ops" / "SKILL.md"


def test_frontmatter_names_the_skill():
    text = SKILL.read_text()
    assert text.startswith("---\nname: ops\n")
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
        "routes_to",
        "expand_graph",
    ):
        assert f"`{tool}`" in text
        assert tool in served


def test_every_command_and_flag_the_skill_runs_exists():
    text = SKILL.read_text()
    for command in ("briefing compose", "graph check-solution"):
        assert f"admiralty {command}" in text
    for flag in ("--expansion-id", "--workspace"):
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
    assert "admiralty:ops" in text
    assert re.search(r"^name: ops$", SKILL.read_text(), re.MULTILINE)


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


def test_a_stale_save_goes_on_when_the_player_asks_for_it():
    step = re.search(r"1\. \*\*Save age\.\*\*(.*?)\n2\. ", SKILL.read_text(), re.DOTALL).group(1)
    step = " ".join(step.split())
    assert "work with this save" in step
    assert "age in one sentence" in step
    assert "Never stop for good on a stale save" in step


def test_text_and_graph_have_separate_jobs():
    text = " ".join(SKILL.read_text().replace("**", "").split())
    assert "Text and graph have separate jobs" in text
    assert "answers the Player's wishes" in text
    assert "what is not possible and why" in text
    assert "Never repeat a Key Action in the text" in text
    assert "Never describe the graph" in text
    assert "Key Actions stand in the graph and in the list under it" in text
    steps = re.search(r"6\. \*\*Key Actions\.\*\*(.*?)\n## ", SKILL.read_text(), re.DOTALL).group(1)
    assert "Action Plan.** By domain" not in steps


def test_there_is_one_current_briefing_that_updates():
    text = " ".join(SKILL.read_text().split())
    assert "## One current Briefing" in text
    assert (
        "briefings/current/overlay.json" in text and "briefings/current/solution-graph.json" in text
    )
    assert "briefings/history/" in text
    assert "briefings/draft/overlay.json" in text
    assert "a second Briefing" not in text
    assert "briefings/<date>" not in text and "--out" not in text
    assert "Never move, rename or delete Briefing files by hand" in text


def test_compose_opens_the_graph_page_and_the_skill_says_what_to_tell_the_player():
    text = " ".join(SKILL.read_text().split())
    assert "`compose` also opens the graph page in the Player's browser" in text
    assert "`opened: true`" in text and "`opened: false`" in text and "`url: null`" in text
    assert "briefing view" not in text


def test_a_model_goal_carries_a_mark_of_its_own():
    text = " ".join(SKILL.read_text().split())
    assert "carries a `mark` of its own" in text
    assert '`up` for "more", `down` for "less", `flag` for a state to reach' in text
    assert "`compose` refuses a model Goal without one" in text


def test_a_node_about_another_empire_names_it():
    text = " ".join(SKILL.read_text().split())
    assert '`"empire": "<its name>"`' in text
    assert "`empires` of the expansion" in text
    assert "Never write `flag` yourself" in text
