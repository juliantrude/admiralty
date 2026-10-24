"""The Stop hook (M7): stdin JSON in, stdout JSON out, `blocks.jsonl`, loop guard, crash safety.

The hook input fields are the ones probed on Claude Code (`docs/plans/M7.md`, open risks).
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from hlidskjalf.claims import hook
from hlidskjalf.cli import main

ROOT = Path(__file__).parent.parent
DISTRICTS = {"tool": "economy", "result": {"districts": {"city": 11}, "unity": {"stock": 2794.45}}}


def make_workspace(tmp_path: Path, entries=(DISTRICTS,)) -> Path:
    workspace = tmp_path / "ws"
    (workspace / ".hlidskjalf").mkdir(parents=True)
    (workspace / "campaign.yaml").write_text("version: 1\n", encoding="utf-8")
    lines = [json.dumps(entry) for entry in entries]
    (workspace / ".hlidskjalf" / "turn-log.jsonl").write_text(
        "".join(line + "\n" for line in lines), encoding="utf-8"
    )
    return workspace


def event(workspace: Path, answer: str, **extra) -> dict:
    return {
        "session_id": "s1",
        "prompt_id": "p1",
        "cwd": str(workspace),
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": answer,
        **extra,
    }


def run(payload) -> tuple[int, dict | None]:
    stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
    stdout = io.StringIO()
    code = hook.stop(stdin, stdout)
    text = stdout.getvalue()
    return code, json.loads(text) if text else None


def blocks(workspace: Path) -> list[dict]:
    path = workspace / ".hlidskjalf" / "blocks.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --- decisions --------------------------------------------------------------------------------


def test_an_answer_with_checked_figures_passes_silently(tmp_path):
    workspace = make_workspace(tmp_path)
    assert run(event(workspace, "You have 11 city districts.")) == (0, None)
    assert blocks(workspace) == []


def test_a_planted_wrong_district_count_is_blocked_and_logged(tmp_path):
    workspace = make_workspace(tmp_path)
    code, output = run(event(workspace, "You have 12 city districts."))
    assert code == 0
    assert output["decision"] == "block"
    reason = output["reason"]
    assert '"12"' in reason and "You have 12 city districts." in reason
    assert "nearest value in the tool results: 11" in reason
    assert "show the addends" in reason and "Do not mention this check" in reason
    (line,) = blocks(workspace)
    assert (line["session_id"], line["prompt_id"]) == ("s1", "p1")
    assert (line["stop_hook_active"], line["released"]) == (False, False)
    assert len(line["answer_hash"]) == 16 and line["claims_checked"] == 1
    (claim,) = line["unverified"]
    assert (claim["kind"], claim["text"], claim["code"], claim["nearest"]) == (
        "number",
        "12",
        "near_match",
        "11",
    )


def test_an_answer_without_numbers_or_names_always_passes(tmp_path):
    workspace = make_workspace(tmp_path, entries=())
    assert run(event(workspace, "Build more farms.")) == (0, None)


def test_the_players_own_figures_are_evidence(tmp_path):
    workspace = make_workspace(tmp_path, entries=())
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-10-24T09:00:00.000Z",
                "message": {"role": "user", "content": "I have 14 city districts, why so few?"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert run(event(workspace, "Yes, 14 city districts.", transcript_path=str(transcript))) == (
        0,
        None,
    )


def test_tool_results_before_the_session_start_are_not_evidence(tmp_path):
    old = {"ts": "2026-01-01T00:00:00+00:00", **DISTRICTS}
    new = {"ts": "2026-10-24T09:01:00+00:00", "tool": "x", "result": {"a": 1}}
    workspace = make_workspace(tmp_path, entries=(old, new))
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps({"type": "queue-operation", "timestamp": "2026-10-24T09:00:00.000Z"}) + "\n",
        encoding="utf-8",
    )
    _, output = run(event(workspace, "11 city districts.", transcript_path=str(transcript)))
    assert output["decision"] == "block"


def test_the_final_answer_comes_from_the_transcript_when_the_input_lacks_it(tmp_path):
    workspace = make_workspace(tmp_path)
    transcript = tmp_path / "t.jsonl"
    entries = [
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "Earlier 99."}]},
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "You have 14 city districts."},
                    {"type": "tool_use", "name": "x", "input": {}},
                ],
            },
        },
        {"type": "user", "message": {"role": "user", "content": "thanks"}},
    ]
    transcript.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    payload = event(workspace, "", transcript_path=str(transcript))
    del payload["last_assistant_message"]
    _, output = run(payload)
    assert output["decision"] == "block" and '"14"' in output["reason"]
    assert "99" not in output["reason"]


def test_a_long_list_of_findings_is_cut_in_the_reason(tmp_path):
    workspace = make_workspace(tmp_path, entries=())
    answer = " ".join(f"Fleet {n} has {n + 500} ships." for n in range(1, 13))
    _, output = run(event(workspace, answer))
    assert output["reason"].startswith("24 unverified")
    assert "and 16 more" in output["reason"]


# --- the loop guard ---------------------------------------------------------------------------


def test_the_hook_blocks_twice_then_releases_with_a_notice(tmp_path):
    workspace = make_workspace(tmp_path)
    wrong = "You have 14 city districts."
    _, first = run(event(workspace, wrong))
    _, second = run(event(workspace, wrong, stop_hook_active=True))
    code, third = run(event(workspace, wrong, stop_hook_active=True))
    assert first["decision"] == second["decision"] == "block"
    assert code == 0 and "decision" not in third
    assert "could not verify" in third["systemMessage"]
    assert [(b["stop_hook_active"], b["released"]) for b in blocks(workspace)] == [
        (False, False),
        (True, False),
        (True, True),
    ]


def test_a_new_answer_starts_counting_again(tmp_path):
    workspace = make_workspace(tmp_path)
    wrong = "You have 14 city districts."
    for _ in range(3):
        run(event(workspace, wrong, stop_hook_active=True))
    _, output = run(event(workspace, wrong, prompt_id="p2"))
    assert output["decision"] == "block"
    _, output = run(event(workspace, wrong, prompt_id="p2", stop_hook_active=True))
    assert output["decision"] == "block"


def test_a_rewritten_answer_that_checks_out_passes_after_a_block(tmp_path):
    workspace = make_workspace(tmp_path)
    run(event(workspace, "You have 14 city districts."))
    assert run(event(workspace, "You have 11 city districts.", stop_hook_active=True)) == (0, None)


# --- where it runs and how it fails -----------------------------------------------------------


def test_outside_a_campaign_workspace_the_hook_allows_silently(tmp_path):
    elsewhere = tmp_path / "other"
    elsewhere.mkdir()
    assert run(event(elsewhere, "You have 14 city districts.")) == (0, None)
    assert not (elsewhere / ".hlidskjalf").exists()


def test_the_workspace_is_found_from_a_subdirectory(tmp_path):
    workspace = make_workspace(tmp_path)
    sub = workspace / "notes" / "deep"
    sub.mkdir(parents=True)
    _, output = run(event(sub, "You have 14 city districts."))
    assert output["decision"] == "block"
    assert len(blocks(workspace)) == 1


def test_a_directory_with_only_a_config_or_only_the_state_dir_is_no_workspace(tmp_path):
    only_config = tmp_path / "a"
    only_config.mkdir()
    (only_config / "campaign.yaml").write_text("x: 1\n", encoding="utf-8")
    only_state = tmp_path / "b" / ".hlidskjalf"
    only_state.mkdir(parents=True)
    assert hook.find_workspace(only_config) is None
    assert hook.find_workspace(only_state.parent) is None


@pytest.mark.parametrize("payload", ["", "not json", "[1, 2]", "null", '{"cwd": 5}', "{}"])
def test_unreadable_input_allows(payload):
    assert run(payload) == (0, None)


def test_a_crash_still_exits_0_without_a_block_and_is_logged(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("index exploded")

    monkeypatch.setattr(hook, "check_answer", boom)
    assert run(event(workspace, "You have 14 city districts.")) == (0, None)
    log = (workspace / ".hlidskjalf" / "hook-errors.log").read_text(encoding="utf-8")
    assert "RuntimeError: index exploded" in log
    assert blocks(workspace) == []


def test_a_broken_turn_log_or_transcript_does_not_block_a_good_answer(tmp_path):
    workspace = make_workspace(tmp_path)
    (workspace / ".hlidskjalf" / "turn-log.jsonl").write_text("{broken\n", encoding="utf-8")
    payload = event(workspace, "Build more farms.", transcript_path=str(tmp_path / "missing"))
    assert run(payload) == (0, None)


# --- through the command line, like Claude Code runs it --------------------------------------


def test_cli_hook_stop_reads_stdin_and_prints_the_decision(tmp_path, monkeypatch, capsys):
    workspace = make_workspace(tmp_path)
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps(event(workspace, "14 city districts.")))
    )
    assert main(["hook", "stop"]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "block"


def test_the_installed_command_blocks_in_a_subprocess(tmp_path):
    workspace = make_workspace(tmp_path)
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from hlidskjalf.cli import main; sys.exit(main())",
            "hook",
            "stop",
        ],
        input=json.dumps(event(workspace, "You have 14 city districts.")),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["decision"] == "block"


# --- wiring -----------------------------------------------------------------------------------


def test_hooks_json_runs_the_stop_command_that_the_cli_serves():
    config = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    (group,) = config["hooks"]["Stop"]
    (entry,) = group["hooks"]
    assert entry["type"] == "command" and entry["command"] == "uv"
    args = entry["args"]
    assert args[:4] == ["run", "--quiet", "--project", "${CLAUDE_PLUGIN_ROOT}"]
    assert args[4:] == ["hlidskjalf", "hook", "stop"]
    assert entry["timeout"] >= 10


def test_the_plugin_manifest_names_the_hooks_file():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["hooks"] == "./hooks/hooks.json"
    assert (ROOT / manifest["hooks"]).is_file()
