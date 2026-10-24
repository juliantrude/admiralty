"""Unverified Claim check, second half (M7): matching an answer against the turn log.

Synthetic turn logs only; the reference Briefings come with the verification increment.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from hlidskjalf.claims.check import check_answer
from hlidskjalf.claims.evidence import build_evidence, read_transcript, read_turn_log
from hlidskjalf.cli import main

RESULTS = [
    {
        "tool": "economy",
        "result": {
            "unity": {"stock": 2794.45, "net": 18.2},
            "energy": {"net": 88, "income": 7412.0},
            "pop": {"unemployed": 0.15, "total": 1234},
            "date": "2259.12.25",
            "planets": [{"name": "Nibiru"}, {"name": "Kolonie Alpha"}, {"name": "Tier 2"}],
            "districts": {"city": 11},
        },
    },
    {
        "tool": "expand_graph",
        "result": {
            "nodes": [{"id": "unity.more", "title": "More Unity"}],
            "playbook_rules": {
                "unity-vs-next-tradition": {
                    "reason": "Unity buys 1 tradition per 4384 Unity",
                    "body": "Do not spend on edicts.",
                }
            },
        },
    },
]


def verdict(answer: str, entries=RESULTS, player=()):
    return check_answer(answer, build_evidence(entries, player))


def codes(answer: str, **kwargs) -> list[tuple[str, str]]:
    return [(u.claim.text, u.code) for u in verdict(answer, **kwargs).unverified]


# --- numbers ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "Unity stock is 2794.45.",
        "Unity stock is 2794.",  # rounded at the stated precision
        "Unity stock is 2,794.45 and 2.794,45 in German.",
        "Unity stock is 2.8k.",
        "Energy income is 7.4k.",
        "Unity net is -18.2 per month.",  # sign ignored
        "Unity net is +18.",
        "Unemployed pops: 15 %.",  # ratio 0.15 as percent
        "Unemployed pops: 15%.",
        "Total pops 1234 (1.234 in German).",
        "Energy net 88.",
        "The empire has 3 planets.",  # length of a list of records
        "11 city districts.",
    ],
)
def test_figures_found_in_the_data_pass(answer):
    assert codes(answer) == []


def test_a_wrong_number_is_blocked_with_the_nearest_data_value():
    (finding,) = verdict("The empire has 12 city districts.").unverified
    assert (finding.claim.text, finding.code) == ("12", "near_match")
    assert str(finding.nearest) == "11"
    assert "economy#1" in finding.nearest_source and "districts" in finding.nearest_source


def test_a_number_nowhere_near_the_data_has_no_match_and_no_nearest():
    (finding,) = verdict("The empire has 400 city districts.").unverified
    assert (finding.code, finding.nearest) == ("no_match", None)


def test_precision_is_the_claims_own():
    assert codes("Stock 2794.4.") == [("2794.4", "near_match")]  # data 2794.45 rounds to 2794.5
    assert codes("Stock 2794.5.") == []
    assert codes("Stock 2790.") == [("2790", "near_match")]


def test_an_ambiguous_reading_passes_when_either_matches():
    entries = [{"tool": "x", "result": {"a": 2.794, "b": 5}}]
    assert codes("It is 2.794.", entries=entries) == []
    entries = [{"tool": "x", "result": {"a": 2794}}]
    assert codes("It is 2.794.", entries=entries) == []
    assert codes("It is 2.795.", entries=entries) != []


def test_numbers_inside_evidence_strings_count():
    entries = [{"tool": "x", "result": {"text": "Unity 2794.45 < next Tradition 4384"}}]
    assert codes("The next Tradition costs 4384.", entries=entries) == []


def test_errors_are_no_evidence():
    entries = [{"tool": "economy", "result": {"error": "no save, tried 777"}}]
    assert codes("There are 777.", entries=entries) == [("777", "no_match")]


def test_no_tool_results_at_all():
    assert codes("The stock is 2794.", entries=[]) == [("2794", "no_match")]
    assert verdict("Nothing to compute here.", entries=[]).ok


def test_player_input_counts():
    assert codes("You said 9171 planets.") == [("9171", "no_match")]
    assert codes("You said 9171 planets.", player=["Ich habe 9171 Planeten"]) == []


# --- derived figures --------------------------------------------------------------------------

SUMS = [{"tool": "r", "result": {"a": 88, "b": 74.77, "c": 67.59, "d": 20}}]


def test_a_sum_with_shown_addends_passes():
    assert codes("- Research total 230.36 (88 + 74.77 + 67.59)", entries=SUMS) == []


def test_a_difference_with_shown_addends_passes():
    assert codes("- Net 68: 88 - 20 gives 68.", entries=SUMS) == []


def test_the_same_total_without_addends_is_blocked():
    assert codes("- Research total 230.36", entries=SUMS) == [("230.36", "no_match")]


def test_a_wrong_total_with_addends_is_blocked_as_derived_unexplained():
    assert codes("- Research total 300.36 (88 + 74.77 + 67.59)", entries=SUMS) == [
        ("300.36", "derived_unexplained")
    ]


def test_addends_must_stand_in_the_same_unit():
    answer = "- Research total 230.36\n- Parts 88, 74.77 and 67.59\n"
    assert codes(answer, entries=SUMS) == [("230.36", "no_match")]


def test_a_total_must_show_addends_that_are_themselves_in_the_data():
    answer = "- Total 15 (10 + 5)"
    assert codes(answer, entries=SUMS) == [
        ("15", "no_match"),
        ("10", "no_match"),
        ("5", "no_match"),
    ]


def test_a_percentage_of_two_shown_numbers_passes():
    entries = [{"tool": "r", "result": {"used": 11, "cap": 40}}]
    assert codes("- 11 of 40 used, 27.5%", entries=entries) == []
    assert codes("- 11 of 40 used, 35%", entries=entries) == [("35%", "derived_unexplained")]


def test_a_product_is_not_derived():
    entries = [{"tool": "r", "result": {"a": 6, "b": 7}}]
    assert codes("- 6 times 7 is 42", entries=entries) == [("42", "derived_unexplained")]


# --- exemptions and the other claim kinds -----------------------------------------------------


def test_a_quoted_rule_may_hold_its_own_figures():
    answer = "> Unity kauft 1 Tradition je 9999 Unity.\n"
    assert codes(answer) == []
    assert codes(answer, entries=RESULTS[:1]) != []  # no rule in the results: no exemption


def test_names_must_be_in_the_data():
    assert codes("Build in **Nibiru** and **Kolonie Alphas**.") == []
    assert codes("Build in **Atlantis**.") == [("Atlantis", "name_no_match")]
    assert codes("Goal `unity.more`, rule `unity-vs-next-tradition`.") == []
    assert codes("Goal `unity.fewer`.") == [("unity.fewer", "name_no_match")]


def test_names_match_inside_longer_evidence_text_as_whole_words():
    assert codes("Ignore **Not Spend** here.") == []  # inside "Do not spend on edicts."
    assert codes("Ignore **Not Spen** here.") == [("Not Spen", "name_no_match")]


def test_player_names_count():
    assert codes("Look at **Atlantis**.", player=["Ich spiele auf Atlantis"]) == []


def test_a_number_in_a_name_stands_with_the_name():
    assert codes("Look at **Tier 2**.") == []
    assert codes("Look at **Tier 9**.") == [("Tier 9", "name_no_match")]


def test_dates_match_as_whole_strings():
    assert codes("On 2259.12.25 it was so.") == []
    assert codes("On 2259.12.26 it was so.") == [("2259.12.26", "no_match")]


def test_an_answer_without_figures_or_names_passes():
    assert verdict("Das war ein guter Zug, baue weiter so.").ok


# --- reading the session ----------------------------------------------------------------------


def write_log(workspace, entries):
    log = workspace / ".hlidskjalf" / "turn-log.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text("".join(json.dumps(e) + "\n" for e in entries) + "not json\n")


def test_the_window_starts_at_the_given_time(tmp_path):
    old = {"ts": "2026-10-24T08:00:00+00:00", "tool": "a", "result": {"v": 111}}
    new = {"ts": "2026-10-24T10:00:00+00:00", "tool": "a", "result": {"v": 222}}
    write_log(tmp_path, [old, new])
    assert len(read_turn_log(tmp_path)) == 2  # the broken line is skipped
    since = datetime(2026, 10, 24, 9, tzinfo=UTC)
    assert [e["result"]["v"] for e in read_turn_log(tmp_path, since)] == [222]
    assert len(read_turn_log(tmp_path, datetime(2026, 10, 24, 9))) == 1  # naive = UTC
    assert read_turn_log(tmp_path / "none") == []


def test_the_transcript_gives_the_players_messages_only(tmp_path):
    lines = [
        {"type": "user", "timestamp": "2026-10-24T09:00:00Z", "message": {"content": "Ich: 4711"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "assistant 1"}]}},
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "tool 2"}]},
        },
        {"type": "user", "isMeta": True, "message": {"content": "skill text 3"}},
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "text",
                        "text": "Zweite 5<system-reminder>reminder 6</system-reminder>",
                    }
                ]
            },
        },
    ]
    path = tmp_path / "t.jsonl"
    path.write_text("".join(json.dumps(x) + "\n" for x in lines) + "garbage\n")
    started, texts = read_transcript(path)
    assert started == datetime(2026, 10, 24, 9, tzinfo=UTC)
    assert texts == ["Ich: 4711", "Zweite 5"]
    assert read_transcript(tmp_path / "missing") == (None, [])


def test_the_verdict_serialises(tmp_path):
    out = verdict("12 city districts and **Atlantis**.").to_dict()
    assert out["ok"] is False and out["claims"] == 2
    assert {u["code"] for u in out["unverified"]} == {"near_match", "name_no_match"}
    json.dumps(out)


# --- the CLI ----------------------------------------------------------------------------------


def test_cli_check_exit_codes(tmp_path, capsys):
    write_log(tmp_path, [{"ts": "2026-10-24T10:00:00+00:00", **RESULTS[0]}])
    answer = tmp_path / "answer.md"
    command = ["claims", "check", "--workspace", str(tmp_path), "--answer", str(answer)]
    answer.write_text("11 city districts in **Nibiru**.")
    assert main(command) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    answer.write_text("17 city districts.")
    assert main(command) == 1
    assert json.loads(capsys.readouterr().out)["unverified"][0]["code"] == "near_match"
    with pytest.raises(SystemExit, match="claims"):
        main(["claims", "check", "--workspace", str(tmp_path), "--answer", str(tmp_path / "no")])


def test_cli_uses_the_transcript_for_player_input_and_window(tmp_path, capsys):
    write_log(tmp_path, [{"ts": "2026-10-24T10:00:00+00:00", **RESULTS[0]}])
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps(
            {"type": "user", "timestamp": "2026-10-24T11:00:00Z", "message": {"content": "4711"}}
        )
        + "\n"
    )
    answer = tmp_path / "answer.md"
    answer.write_text("You wrote 4711 and the stock is 2794.45.")
    command = ["claims", "check", "--workspace", str(tmp_path), "--answer", str(answer)]
    # the transcript starts after the only turn log entry: the stock is outside the window
    assert main([*command, "--transcript", str(transcript)]) == 1
    unverified = json.loads(capsys.readouterr().out)["unverified"]
    assert [u["text"] for u in unverified] == ["2794.45"]
    assert main([*command, "--transcript", str(transcript), "--since", "2026-10-24T09:00"]) == 0
