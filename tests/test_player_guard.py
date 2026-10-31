"""The PreToolUse hook (M9, 20a): Write, Edit and Bash on player-model/ are refused."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from admiralty.cli import main
from admiralty.player import guard, store

ROOT = Path(__file__).parent.parent


def run(payload) -> tuple[int, dict | None]:
    stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
    stdout = io.StringIO()
    code = guard.pretooluse(stdin, stdout)
    text = stdout.getvalue()
    return code, json.loads(text) if text else None


def call(tool, cwd, **arguments):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": arguments,
        "cwd": str(cwd),
    }


def denied(output) -> bool:
    return output is not None and output["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
@pytest.mark.parametrize("name", ["model.json", "events.jsonl", "sub/new.txt", ""])
def test_writing_inside_the_folder_is_denied(tmp_path, tool, name):
    target = store.model_dir() / name
    code, output = run(call(tool, tmp_path, file_path=str(target)))
    assert code == 0 and denied(output)
    assert "Academy tools" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_relative_path_and_a_dotdot_path_are_resolved(tmp_path):
    folder = store.model_dir()
    folder.mkdir(parents=True)
    assert denied(run(call("Write", folder, file_path="model.json"))[1])
    assert denied(
        run(call("Write", tmp_path, file_path=str(folder / "x" / ".." / "model.json")))[1]
    )


def test_a_symlink_into_the_folder_is_followed(tmp_path):
    folder = store.model_dir()
    folder.mkdir(parents=True)
    link = tmp_path / "shortcut"
    link.symlink_to(folder)
    assert denied(run(call("Edit", tmp_path, file_path=str(link / "model.json")))[1])


def test_other_files_pass(tmp_path, data_dir):
    for path in (
        tmp_path / "notes.md",
        data_dir / "workspaces.json",
        data_dir / "player-model-old",
    ):
        assert run(call("Write", tmp_path, file_path=str(path))) == (0, None)


@pytest.mark.parametrize(
    "command",
    [
        "echo '{}' > {dir}/model.json",
        "rm -rf {dir}",
        "sed -i s/understand/create/ {dir}/events.jsonl",
        "cd ~/.local/share/admiralty/player-model && rm model.json",
        "python3 -c \"open('player-model/events.jsonl','a')\"",
        "tee player-model/model.json",
    ],
)
def test_bash_naming_the_folder_is_denied(tmp_path, command):
    command = command.replace("{dir}", str(store.model_dir()))
    assert denied(run(call("Bash", tmp_path, command=command))[1])


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "uv run pytest",
        "git commit -m 'player models'",
        "echo player-modeling",
        "rm my-player-model-x",
    ],
)
def test_other_bash_commands_pass(tmp_path, command):
    assert run(call("Bash", tmp_path, command=command)) == (0, None)


def test_tools_that_do_not_write_pass(tmp_path):
    assert run(call("Read", tmp_path, file_path=str(store.model_dir() / "model.json"))) == (0, None)
    assert run(call("Grep", tmp_path, pattern="x", path=str(store.model_dir()))) == (0, None)


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not json",
        "[1]",
        "null",
        "{}",
        '{"tool_name": "Bash"}',
        '{"tool_name": "Bash", "tool_input": []}',
    ],
)
def test_unreadable_input_allows(payload):
    assert run(payload) == (0, None)


def test_a_crash_lets_the_call_through(tmp_path, monkeypatch):
    def boom(event):
        raise RuntimeError("exploded")

    monkeypatch.setattr(guard, "touches_player_model", boom)
    target = store.model_dir() / "model.json"
    assert run(call("Write", tmp_path, file_path=str(target))) == (0, None)


def test_cli_hook_pretooluse_reads_stdin_and_prints_the_denial(tmp_path, monkeypatch, capsys):
    target = store.model_dir() / "model.json"
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps(call("Write", tmp_path, file_path=str(target))))
    )
    assert main(["hook", "pretooluse"]) == 0
    assert denied(json.loads(capsys.readouterr().out))


def test_the_process_exits_0_and_denies_like_claude_code_runs_it(tmp_path, data_dir):
    target = data_dir / "player-model" / "model.json"
    done = subprocess.run(
        [sys.executable, "-m", "admiralty.cli", "hook", "pretooluse"],
        input=json.dumps(call("Write", tmp_path, file_path=str(target))),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**__import__("os").environ, "ADMIRALTY_DATA_DIR": str(data_dir)},
    )
    assert done.returncode == 0 and denied(json.loads(done.stdout))


def test_the_plugin_registers_the_hook_for_the_writing_tools():
    registered = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    (entry,) = registered["PreToolUse"]
    assert set(entry["matcher"].split("|")) == {
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "Bash",
    }
    (command,) = entry["hooks"]
    assert command["args"][-3:] == ["admiralty", "hook", "pretooluse"]
    assert "Stop" in registered
