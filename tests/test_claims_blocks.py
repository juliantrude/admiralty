"""`blocks summary` and the review-blocks skill (M7): grouping of a fixture `blocks.jsonl`."""

from __future__ import annotations

import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path

from hlidskjalf.claims.blocks import summarise
from hlidskjalf.cli import main

ROOT = Path(__file__).parent.parent
SKILL = ROOT / "skills" / "review-blocks" / "SKILL.md"


def finding(kind, code, text, sentence, nearest=None):
    return {
        "kind": kind,
        "code": code,
        "text": text,
        "sentence": sentence,
        "nearest": nearest,
        "nearest_source": None,
    }


def block(prompt, findings, released=False):
    return {
        "ts": "2026-10-24T10:00:00+00:00",
        "session_id": "s1",
        "prompt_id": prompt,
        "stop_hook_active": released,
        "released": released,
        "claims_checked": 5,
        "unverified": findings,
    }


def write_log(tmp_path: Path, lines: list[str]) -> Path:
    workspace = tmp_path / "ws"
    (workspace / ".hlidskjalf").mkdir(parents=True)
    (workspace / ".hlidskjalf" / "blocks.jsonl").write_text(
        "".join(line + "\n" for line in lines), encoding="utf-8"
    )
    return workspace


def fixture_log(tmp_path: Path) -> Path:
    lines = [
        block("p1", [finding("number", "no_match", "42", "There are 42 districts.")]),
        block(
            "p1",
            [
                finding("number", "no_match", "42", "There are 42 districts again."),
                finding("name", "name_no_match", "Hangar 3", "Build **Hangar 3**."),
            ],
        ),
        block(
            "p2",
            [finding("number", "near_match", "2.8k", "Unity is 2.8k.", nearest="2794.45")],
            released=True,
        ),
        block("p3", [finding("number", "derived_unexplained", "30", "Total 30.")]),
    ]
    return write_log(tmp_path, [json.dumps(line) for line in lines])


def test_no_log_is_an_empty_summary(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / ".hlidskjalf").mkdir(parents=True)
    result = summarise(workspace)
    assert result["blocks"] == 0 and result["claims"] == 0
    assert result["groups"] == [] and result["released"] == []


def test_claims_are_grouped_by_kind_and_reason_code_largest_first(tmp_path):
    result = summarise(fixture_log(tmp_path))
    assert result["blocks"] == 4 and result["claims"] == 5
    assert result["by_kind"] == {"name": 1, "number": 4}
    assert [(g["kind"], g["code"], g["count"]) for g in result["groups"]] == [
        ("number", "no_match", 2),
        ("name", "name_no_match", 1),
        ("number", "derived_unexplained", 1),
        ("number", "near_match", 1),
    ]


def test_a_group_holds_the_answer_sentence_of_each_claim(tmp_path):
    group = summarise(fixture_log(tmp_path))["groups"][0]
    assert [e["sentence"] for e in group["examples"]] == [
        "There are 42 districts.",
        "There are 42 districts again.",
    ]
    assert group["examples"][0]["session_id"] == "s1"
    assert group["examples"][0]["prompt_id"] == "p1"


def test_released_blocks_are_listed_apart_with_their_sentences(tmp_path):
    result = summarise(fixture_log(tmp_path))
    assert result["released"] == [
        {
            "ts": "2026-10-24T10:00:00+00:00",
            "session_id": "s1",
            "prompt_id": "p2",
            "claims": 1,
            "sentences": ["Unity is 2.8k."],
        }
    ]
    near = next(g for g in result["groups"] if g["code"] == "near_match")
    assert near["examples"][0]["released"] is True
    assert near["examples"][0]["nearest"] == "2794.45"


def test_unreadable_lines_are_counted_and_do_not_stop_the_summary(tmp_path):
    good = json.dumps(block("p1", [finding("number", "no_match", "42", "42 districts.")]))
    workspace = write_log(tmp_path, ["{not json", good, "[1, 2]", ""])
    result = summarise(workspace)
    assert result["unreadable_lines"] == 2
    assert result["blocks"] == 1 and result["claims"] == 1


def test_examples_per_group_are_capped_but_counted(tmp_path):
    lines = [
        json.dumps(block(f"p{n}", [finding("number", "no_match", "1", f"Sentence {n}.")]))
        for n in range(30)
    ]
    group = summarise(write_log(tmp_path, lines))["groups"][0]
    assert group["count"] == 30 and len(group["examples"]) == 20


def test_the_cli_prints_the_summary_as_json(tmp_path):
    workspace = fixture_log(tmp_path)
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(["blocks", "summary", "--workspace", str(workspace)])
    assert code == 0
    assert json.loads(out.getvalue()) == summarise(workspace)


# --- the skill ------------------------------------------------------------------------------------


def test_frontmatter_names_the_skill():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: review-blocks\n")
    assert re.search(r"^description: .{40,}", text, re.MULTILINE)


def test_every_command_and_flag_the_skill_runs_exists():
    text = SKILL.read_text(encoding="utf-8")
    commands = set(re.findall(r"hlidskjalf (\w+(?: [\w-]+)?)", text))
    assert commands == {"blocks summary"}
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            main(["blocks", "summary", "--help"])
    except SystemExit:
        pass
    assert "--workspace" in text and "--workspace" in out.getvalue()


def test_the_skill_names_every_reason_code_and_summary_field():
    text = SKILL.read_text(encoding="utf-8")
    for code in ("no_match", "near_match", "derived_unexplained", "name_no_match", "released"):
        assert f"`{code}`" in text
    summary = summarise_keys()
    for key in summary:
        assert f"`{key}`" in text


def summarise_keys() -> set[str]:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        (workspace / ".hlidskjalf").mkdir()
        return set(summarise(workspace))


def test_the_skill_only_proposes_and_writes_one_file():
    text = SKILL.read_text(encoding="utf-8")
    assert "You **propose**; you never edit code, `knowledge/` or tests" in text
    assert "Write to nothing outside `docs/proposals/claims.md`" in text
    assert "docs/proposals/claims.md" in text


def test_the_proposals_file_exists_and_only_proposes():
    # It started empty (M7 increment 5) and gained its first section in M7 verification:
    # either the placeholder or sections that say nothing is applied.
    text = (ROOT / "docs" / "proposals" / "claims.md").read_text(encoding="utf-8")
    assert text.startswith("# Proposed changes to the Unverified Claim check")
    assert "Nothing here\nis applied" in text
    assert "_No proposals yet._" in text or "\n## " in text
