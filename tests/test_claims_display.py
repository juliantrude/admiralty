"""The MessageDisplay hook: answers appear only once the Stop hook passed them."""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path

import pytest
from test_claims_hook import event, make_workspace, reason_of, run

from admiralty.claims import display
from admiralty.cli import main


def batch(workspace: Path, index: int, delta: str, final: bool, message: str = "m1") -> dict:
    return {
        "session_id": "s1",
        "cwd": str(workspace),
        "message_id": message,
        "index": index,
        "delta": delta,
        "final": final,
    }


def no_wait(event_: dict, workspace: Path) -> str:
    return display.hold(event_, workspace, window_s=0, deadline_s=0)


def test_without_stop_the_whole_message_appears(tmp_path):
    """Text before a tool call: Stop never comes."""
    workspace = make_workspace(tmp_path)
    assert no_wait(batch(workspace, 0, "one\n", False), workspace) == ""
    assert no_wait(batch(workspace, 1, "two\n", False), workspace) == ""
    assert no_wait(batch(workspace, 2, "three", True), workspace) == "one\ntwo\nthree"


def test_batches_may_arrive_out_of_order(tmp_path):
    workspace = make_workspace(tmp_path)
    assert no_wait(batch(workspace, 1, "two\n", False), workspace) == ""
    assert no_wait(batch(workspace, 0, "one\n", False), workspace) == ""
    assert no_wait(batch(workspace, 2, "three", True), workspace) == "one\ntwo\nthree"


@pytest.mark.parametrize("show", [True, False])
def test_the_verdict_of_stop_decides(tmp_path, show):
    workspace = make_workspace(tmp_path)
    display.stop_began(workspace, "s1", "Answer\n")
    display.stop_decided(workspace, "s1", "Answer", show)
    assert no_wait(batch(workspace, 0, "Answer", True), workspace) == ("Answer" if show else "")


def test_without_a_verdict_the_message_appears_at_the_deadline(tmp_path):
    workspace = make_workspace(tmp_path)
    display.stop_began(workspace, "s1", "Answer")
    assert no_wait(batch(workspace, 0, "Answer", True), workspace) == "Answer"


def test_the_same_text_later_does_not_inherit_an_old_verdict(tmp_path):
    workspace = make_workspace(tmp_path)
    display.stop_began(workspace, "s1", "Answer")
    display.stop_decided(workspace, "s1", "Answer", False)
    assert no_wait(batch(workspace, 0, "Answer", True), workspace) == ""
    assert no_wait(batch(workspace, 0, "Answer", True, "m2"), workspace) == "Answer"


@pytest.mark.parametrize(
    ("answer", "shown"),
    [
        ("You have 12 city districts.", ""),
        ("You have 11 city districts.", "You have 11 city districts."),
    ],
)
def test_both_hooks_together(tmp_path, answer, shown):
    workspace = make_workspace(tmp_path)
    result: list[str] = []
    holder = threading.Thread(
        target=lambda: result.append(display.hold(batch(workspace, 0, answer, True), workspace))
    )
    holder.start()
    _, output = run(event(workspace, answer))
    holder.join(timeout=10)
    assert bool(reason_of(output)) == (not shown)
    assert result == [shown]


def test_the_released_answer_appears_after_the_last_round(tmp_path):
    workspace = make_workspace(tmp_path)
    wrong = "You have 14 city districts."
    run(event(workspace, wrong))
    run(event(workspace, wrong, stop_hook_active=True))
    _, third = run(event(workspace, wrong, stop_hook_active=True))
    assert "could not verify" in third["systemMessage"]
    assert no_wait(batch(workspace, 0, wrong, True), workspace) == wrong


def test_outside_a_workspace_the_hook_stays_silent(tmp_path, monkeypatch, capsys):
    stdin = io.StringIO(json.dumps(batch(tmp_path, 0, "text", False)))
    monkeypatch.setattr("sys.stdin", stdin)
    assert main(["hook", "display"]) == 0
    assert capsys.readouterr().out == ""


def test_the_cli_serves_the_hook_format(tmp_path, monkeypatch, capsys):
    workspace = make_workspace(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(batch(workspace, 0, "a\n", False))))
    assert main(["hook", "display"]) == 0
    output = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert output == {"hookEventName": "MessageDisplay", "displayContent": ""}
