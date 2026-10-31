"""Epoch candidates, finding candidates and `debrief check-epochs`: constructed series, then the reference Campaign."""

from __future__ import annotations

import json
import os

import pytest
from conftest import SAVES_DIR, VULKAN, reference_save

from admiralty.cli import main
from admiralty.debrief.epochs import (
    build_candidates,
    candidates_for_frame,
    check_epochs,
)
from admiralty.debrief.findings import MAX_PER_INTERVAL, build_findings
from admiralty.debrief.frame import load_campaign, resolve_frame
from admiralty.debrief.series import change
from admiralty.mcp.service import CampaignService
from admiralty.workspace.archive import Archive
from admiralty.workspace.config import CampaignConfig


def interval(start, end, years, wars_started=(), wars_ended=(), lost=(), **values):
    """An interval as `build_intervals` returns it; every value is `(from, to)`."""
    return {
        "from": start,
        "to": end,
        "years": years,
        "values": {name: change(*pair) for name, pair in values.items()},
        "planets_gained": [],
        "planets_lost": list(lost),
        "traditions_adopted": [],
        "ascension_perks_taken": [],
        "wars_started": list(wars_started),
        "wars_ended": list(wars_ended),
    }


def event(date, name, *involves):
    return {"date": date, "event": name, "involves": list(involves)}


def pick(candidates, precision, date, before=None):
    found = [
        c
        for c in candidates
        if c["precision"] == precision and c["date"] == date and c.get("before") == before
    ]
    assert len(found) == 1, (precision, date, before, candidates)
    return found[0]


# --- candidates ------------------------------------------------------------------------------------


def test_the_frame_ends_and_every_timeline_event_are_exact_candidates():
    events = [event("2230.07.17", "War Declared"), event("2245.01.23", "New Colony", "Alpha")]
    candidates = build_candidates(events, [], "2220.04.26", "2259.12.29")
    assert [c["date"] for c in candidates] == [
        "2220.04.26",
        "2230.07.17",
        "2245.01.23",
        "2259.12.29",
    ]
    assert all(c["precision"] == "exact" for c in candidates)
    assert pick(candidates, "exact", "2220.04.26")["reasons"] == ["frame start"]
    assert pick(candidates, "exact", "2259.12.29")["reasons"] == ["frame end"]
    assert pick(candidates, "exact", "2230.07.17")["reasons"] == ["War Declared"]


def test_events_of_one_date_and_the_frame_start_share_one_candidate():
    events = [event("2220.04.26", "New Colony"), event("2220.04.26", "A Law for the Stars")]
    candidates = build_candidates(events, [], "2220.04.26", "2259.12.29")
    assert pick(candidates, "exact", "2220.04.26")["reasons"] == [
        "frame start",
        "New Colony",
        "A Law for the Stars",
    ]


def test_a_war_is_a_between_candidate_for_the_interval_it_shows_in():
    intervals = [
        interval("2259.12.29", "2273.09.07", 13.7, wars_started=["Great War"]),
        interval("2273.09.07", "2284.09.29", 11.0, wars_ended=["Great War"]),
    ]
    candidates = build_candidates([], intervals, "2259.12.29", "2284.09.29")
    started = pick(candidates, "between", "2259.12.29", "2273.09.07")
    assert (started["after"], started["before"]) == ("2259.12.29", "2273.09.07")
    assert started["reasons"] == ["war started: Great War"]
    ended = pick(candidates, "between", "2273.09.07", "2284.09.29")
    assert ended["reasons"] == ["war ended: Great War"]


def test_two_wars_in_one_interval_share_a_candidate():
    candidates = build_candidates(
        [],
        [interval("2200.01.01", "2220.01.01", 20, wars_started=["A", "B"], wars_ended=["C"])],
        "2200.01.01",
        "2220.01.01",
    )
    assert pick(candidates, "between", "2200.01.01", "2220.01.01")["reasons"] == [
        "war started: A",
        "war started: B",
        "war ended: C",
    ]


def test_growth_that_changes_its_pace_by_more_than_a_factor_of_two_is_a_regime_change():
    slow = interval("2200.01.01", "2210.01.01", 10, planets=(2, 4))  # 0.2/yr
    fast = interval("2210.01.01", "2220.01.01", 10, planets=(4, 14))  # 1/yr
    candidates = build_candidates([], [slow, fast], "2200.01.01", "2220.01.01")
    regime = pick(candidates, "between", "2200.01.01", "2220.01.01")
    assert regime["reasons"] == ["planets 0.2/yr -> 1/yr"]


def test_growth_within_a_factor_of_two_is_no_regime_change():
    slow = interval("2200.01.01", "2210.01.01", 10, planets=(2, 4))  # 0.2/yr
    steady = interval("2210.01.01", "2220.01.01", 10, planets=(4, 8))  # 0.4/yr, exactly 2
    candidates = build_candidates([], [slow, steady], "2200.01.01", "2220.01.01")
    assert [c["date"] for c in candidates] == ["2200.01.01", "2220.01.01"]


def test_a_sign_flip_is_a_regime_change_and_a_zero_growth_is_not():
    grow = interval("2200.01.01", "2210.01.01", 10, pops=(100, 120))
    shrink = interval("2210.01.01", "2220.01.01", 10, pops=(120, 118))  # -0.2/yr against 2/yr
    flat = interval("2220.01.01", "2230.01.01", 10, pops=(118, 118))
    candidates = build_candidates([], [grow, shrink, flat], "2200.01.01", "2230.01.01")
    reasons = [r for c in candidates for r in c["reasons"]]
    assert reasons.count("pops 2/yr -> -0.2/yr") == 1
    assert not [r for r in reasons if r.startswith("pops -0.2/yr")]


def test_only_the_regime_series_count():
    slow = interval("2200.01.01", "2210.01.01", 10, traditions=(1, 2), tech_power=(10, 20))
    fast = interval("2210.01.01", "2220.01.01", 10, traditions=(2, 9), tech_power=(20, 90))
    candidates = build_candidates([], [slow, fast], "2200.01.01", "2220.01.01")
    assert [c["date"] for c in candidates] == ["2200.01.01", "2220.01.01"]


def test_candidates_within_a_year_of_each_other_are_all_listed_in_date_order():
    events = [event("2230.07.17", "B"), event("2230.01.01", "A"), event("2230.10.01", "C")]
    candidates = build_candidates(events, [], "2220.01.01", "2240.01.01")
    assert [c["date"] for c in candidates][1:4] == ["2230.01.01", "2230.07.17", "2230.10.01"]


# --- check-epochs ----------------------------------------------------------------------------------

START, END = "2200.01.01", "2298.03.11"
CANDIDATES = build_candidates(
    [event("2230.07.17", "War Declared"), event("2245.01.23", "New Colony")],
    [
        interval("2259.12.29", "2273.09.07", 13.7, wars_started=["Great War"]),
        interval("2273.09.07", "2284.09.29", 11.0, wars_ended=["Great War"]),
    ],
    START,
    END,
)


def epoch(title, start, end, anchor=None, why="because"):
    out = {"title": title, "from": start, "to": end, "why": why}
    if anchor is not None:
        out["anchor"] = anchor
    return out


def exact(date, name):
    return {"date": date, "event": name}


def between(after, before):
    return {"after": after, "before": before}


GOOD = [
    epoch("Peace", START, "2230.07.17"),
    epoch("Expansion", "2230.07.17", "2275.01.01", exact("2230.07.17", "War Declared")),
    epoch("The Great War", "2275.01.01", END, between("2273.09.07", "2284.09.29")),
]


def test_a_good_set_of_epochs_has_no_errors_and_only_the_expected_warning():
    result = check_epochs(GOOD, CANDIDATES, START, END)
    assert result["errors"] == []
    assert result["warnings"] == [
        w for w in result["warnings"] if "lie inside epoch 2 ('Expansion')" in w
    ]


def test_one_epoch_over_the_whole_frame_is_fine():
    result = check_epochs([epoch("Everything", START, END)], CANDIDATES, START, END)
    assert result["errors"] == []


def test_epochs_must_be_a_non_empty_list():
    for bad in ([], {}, None, "x"):
        assert check_epochs(bad, CANDIDATES, START, END)["errors"] == [
            "epochs must be a non-empty list of {title, from, to, anchor, why}"
        ]
    errors = check_epochs(["x"], CANDIDATES, START, END)["errors"]
    assert errors == ["epoch 1: must be an object with title, from, to, anchor, why"]


def test_title_why_and_dates_must_be_present():
    broken = [{"title": " ", "from": "2200-01-01", "to": END}]
    errors = check_epochs(broken, CANDIDATES, START, END)["errors"]
    assert any("title is missing or empty" in e for e in errors)
    assert any("why is missing or empty" in e for e in errors)
    assert any("from must be an in-game date" in e for e in errors)


def test_the_first_epoch_starts_and_the_last_ends_on_the_frame_ends():
    errors = check_epochs([epoch("Short", "2210.01.01", "2290.01.01")], CANDIDATES, START, END)[
        "errors"
    ]
    assert "the first epoch starts 2210.01.01, the frame starts 2200.01.01" in errors
    assert "the last epoch ends 2290.01.01, the frame ends 2298.03.11" in errors


def test_a_gap_and_an_overlap_between_epochs_are_errors():
    gap = [GOOD[0], {**GOOD[1], "to": "2270.01.01"}, GOOD[2]]
    errors = check_epochs(gap, CANDIDATES, START, END)["errors"]
    assert any(
        "gap between epoch 2 (ends 2270.01.01) and epoch 3 (starts 2275.01.01)" in e for e in errors
    )
    overlap = [GOOD[0], {**GOOD[1], "to": "2280.01.01"}, GOOD[2]]
    errors = check_epochs(overlap, CANDIDATES, START, END)["errors"]
    assert any("epochs 2 and 3 overlap" in e for e in errors)


def test_an_epoch_must_have_a_length():
    errors = check_epochs(
        [epoch("A", START, START), epoch("B", START, END, exact(START, "frame start"))],
        CANDIDATES,
        START,
        END,
    )["errors"]
    assert any("from 2200.01.01 is not before to 2200.01.01" in e for e in errors)


def test_a_border_without_a_candidate_names_the_missing_event_or_interval():
    bad = [epoch("A", START, "2240.01.01"), epoch("B", "2240.01.01", END, exact("2240.01.01", "x"))]
    errors = check_epochs(bad, CANDIDATES, START, END)["errors"]
    assert errors == ["epoch 2 ('B'): no Timeline event or archived interval at 2240.01.01"]
    other = [
        epoch("A", START, "2240.01.01"),
        epoch("B", "2240.01.01", END, between("2220.01.01", "2250.01.01")),
    ]
    assert check_epochs(other, CANDIDATES, START, END)["errors"] == errors


def test_a_border_needs_an_anchor():
    bad = [epoch("A", START, "2230.07.17"), epoch("B", "2230.07.17", END)]
    errors = check_epochs(bad, CANDIDATES, START, END)["errors"]
    assert len(errors) == 1 and "has no anchor" in errors[0]


def test_an_anchor_must_name_the_event_that_the_timeline_holds():
    bad = [
        epoch("A", START, "2230.07.17"),
        epoch("B", "2230.07.17", END, exact("2230.07.17", "Peace Treaty")),
    ]
    errors = check_epochs(bad, CANDIDATES, START, END)["errors"]
    assert len(errors) == 1 and "'Peace Treaty'" in errors[0] and "War Declared" in errors[0]


def test_an_exact_anchor_must_be_on_the_border_date():
    bad = [
        epoch("A", START, "2230.07.18"),
        epoch("B", "2230.07.18", END, exact("2230.07.17", "War Declared")),
    ]
    errors = check_epochs(bad, CANDIDATES, START, END)["errors"]
    assert len(errors) == 1 and "is not the border 2230.07.18" in errors[0]


def test_a_between_border_must_lie_inside_its_interval():
    bad = [
        epoch("A", START, "2290.01.01"),
        epoch("B", "2290.01.01", END, between("2273.09.07", "2284.09.29")),
    ]
    errors = check_epochs(bad, CANDIDATES, START, END)["errors"]
    assert len(errors) == 1 and "lies outside the interval 2273.09.07 to 2284.09.29" in errors[0]
    on_edge = [
        epoch("A", START, "2284.09.29"),
        epoch("B", "2284.09.29", END, between("2273.09.07", "2284.09.29")),
    ]
    assert check_epochs(on_edge, CANDIDATES, START, END)["errors"] == []


def test_digits_in_a_title_are_a_warning_not_an_error():
    result = check_epochs([epoch("The 2230 war", START, END)], CANDIDATES, START, END)
    assert result["errors"] == []
    assert any("digits in a title" in w for w in result["warnings"])


def test_a_long_epoch_with_a_timeline_event_inside_is_a_warning():
    result = check_epochs([epoch("Everything", START, END)], CANDIDATES, START, END)
    assert result["errors"] == []
    (warning,) = result["warnings"]
    assert warning.startswith(
        "2230.07.17 War Declared; 2245.01.23 New Colony; 2259.12.29 to 2273.09.07"
    )
    assert "and 1 more" in warning and "98.19 years" in warning


def test_a_short_epoch_draws_no_warning():
    short = [
        epoch("A", START, "2210.01.01"),
        epoch("B", "2210.01.01", END, exact("2210.01.01", "x")),
    ]
    assert check_epochs(short, [], START, END)["errors"]  # no candidate there
    near = [
        epoch("A", "2230.07.17", "2240.01.01", None),
    ]
    assert check_epochs(near, CANDIDATES, "2230.07.17", "2240.01.01")["warnings"] == []


# --- findings --------------------------------------------------------------------------------------


def kinds(findings):
    return [(f["kind"], f["subject"]) for f in findings]


def test_the_biggest_percent_movers_come_first_and_each_finding_carries_the_change():
    findings = build_findings(
        [interval("2200.01.01", "2220.01.01", 20, planets=(2, 3), pops=(100, 300), alloys=(10, 5))]
    )
    assert kinds(findings) == [("gain", "pops"), ("loss", "alloys"), ("gain", "planets")]
    pops = findings[0]
    assert pops["interval"] == {"from": "2200.01.01", "to": "2220.01.01"}
    assert (pops["from"], pops["to"], pops["change"], pops["change_pct"]) == (100, 300, 200, 200.0)


def test_victory_rank_and_wars_running_are_no_percent_movers():
    findings = build_findings(
        [interval("2200.01.01", "2220.01.01", 20, victory_rank=(6, 5), wars_running=(0, 1))]
    )
    assert kinds(findings) == [("rank_change", "victory_rank")]


def test_a_stockpile_that_reached_zero_and_a_net_that_turned_negative_are_discrete_findings():
    findings = build_findings(
        [
            interval(
                "2200.01.01",
                "2220.01.01",
                20,
                **{
                    "Alloys stockpile": (50, 0),
                    "Energy Credits net": (2, -3),
                    "Minerals net": (2, 1),
                },
            )
        ]
    )
    assert {k for k, _ in kinds(findings)[:2]} == {"stockpile_zero", "net_negative"}
    assert ("net_negative", "Minerals net") not in kinds(findings)
    assert ("loss", "Alloys stockpile") in kinds(findings)  # also listed as a mover, after


def test_a_stockpile_at_zero_counts_only_in_the_last_interval_and_with_a_negative_net():
    first = interval(
        "2200.01.01", "2210.01.01", 10, **{"Alloys stockpile": (0, 0), "Alloys net": (0, -1)}
    )
    last = interval(
        "2210.01.01", "2220.01.01", 10, **{"Alloys stockpile": (0, 0), "Alloys net": (0, -1)}
    )
    only_last = [f for f in build_findings([first, last]) if f["kind"] == "stockpile_zero"]
    assert [f["interval"]["from"] for f in only_last] == ["2210.01.01"]
    idle = interval(
        "2210.01.01",
        "2220.01.01",
        10,
        **{"Dark Matter stockpile": (0, 0), "Dark Matter net": (0, 0)},
    )
    assert not [f for f in build_findings([idle]) if f["kind"] == "stockpile_zero"]


def test_lost_planets_are_named():
    findings = build_findings(
        [interval("2200.01.01", "2220.01.01", 20, lost=["Menkar Prime"], planets=(5, 4))]
    )
    lost = next(f for f in findings if f["kind"] == "planets_lost")
    assert lost["names"] == ["Menkar Prime"] and lost["change"] == -1


def test_a_war_that_cost_military_power_needs_a_war_at_one_end_and_a_drop():
    costly = interval(
        "2200.01.01",
        "2220.01.01",
        20,
        wars_started=["Great War"],
        military_power=(1000, 600),
        wars_running=(0, 1),
    )
    cost = next(f for f in build_findings([costly]) if f["kind"] == "war_cost")
    assert cost["change"] == -400 and cost["wars_started"] == ["Great War"]
    peace = interval(
        "2200.01.01", "2220.01.01", 20, military_power=(1000, 600), wars_running=(0, 0)
    )
    assert "war_cost" not in [f["kind"] for f in build_findings([peace])]
    won = interval("2200.01.01", "2220.01.01", 20, military_power=(600, 1000), wars_running=(1, 1))
    assert "war_cost" not in [f["kind"] for f in build_findings([won])]


def test_unemployed_that_grew_faster_than_pops_is_a_finding():
    faster = interval("2200.01.01", "2220.01.01", 20, unemployed=(10, 40), pops=(100, 150))
    found = next(f for f in build_findings([faster]) if f["kind"] == "unemployed_outgrew_pops")
    assert found["change_pct"] == 300.0 and found["pops_change_pct"] == 50.0
    slower = interval("2200.01.01", "2220.01.01", 20, unemployed=(10, 11), pops=(100, 150))
    assert "unemployed_outgrew_pops" not in [f["kind"] for f in build_findings([slower])]
    shrinking = interval("2200.01.01", "2220.01.01", 20, unemployed=(10, 5), pops=(100, 90))
    assert "unemployed_outgrew_pops" not in [f["kind"] for f in build_findings([shrinking])]
    from_zero = interval("2200.01.01", "2220.01.01", 20, unemployed=(0, 3), pops=(100, 150))
    assert "unemployed_outgrew_pops" in [f["kind"] for f in build_findings([from_zero])]


def test_findings_are_capped_per_interval_and_keep_the_largest():
    many = {f"Resource{n:02d} stockpile": (100, 100 + n * 10) for n in range(1, 21)}
    other = {"planets": (4, 5)}
    findings = build_findings(
        [
            interval("2200.01.01", "2220.01.01", 20, **many),
            interval("2220.01.01", "2240.01.01", 20, **other),
        ]
    )
    first = [f for f in findings if f["interval"]["from"] == "2200.01.01"]
    assert len(first) == MAX_PER_INTERVAL
    assert first[0]["subject"] == "Resource20 stockpile"
    assert [f["change_pct"] for f in first] == sorted(
        (f["change_pct"] for f in first), reverse=True
    )
    assert len([f for f in findings if f["interval"]["from"] == "2220.01.01"]) == 1


def test_no_intervals_no_findings():
    assert build_findings([]) == []


# --- the reference Campaign ----------------------------------------------------------------------------

SAVE_NAMES = [
    "2200.01.01", "2220.04.22", "2245.01.23", "2259.12.25",
    "2273.09.03", "2284.09.27", "2288.05.01", "2298.03.11",
]  # fmt: skip


@pytest.fixture(scope="module")
def reference_workspace(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("debrief-epochs")
    for name in SAVE_NAMES:
        reference_save(VULKAN, f"{name}.sav")
    source = tmp_path / "game"
    source.mkdir()
    for name in SAVE_NAMES:
        os.symlink(SAVES_DIR / VULKAN / f"{name}.sav", source / f"{name}.sav")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "campaign.yaml").write_text(f"save_dir: {source}\nempire: Plexxi\nbackup_saves: false\n")
    service = CampaignService(CampaignConfig.load(ws))
    for name in SAVE_NAMES:
        service.empire_overview(name)
    for link in source.iterdir():
        link.unlink()  # Debrief reads the archive alone
    return ws


@pytest.mark.saves
def test_the_reference_candidates_hold_the_war_declared_and_the_war_between_two_dates(
    reference_workspace,
):
    loaded = load_campaign(Archive(reference_workspace))
    frame = resolve_frame(loaded.dates, "all")
    material = candidates_for_frame(loaded, frame)
    candidates = material["candidates"]
    assert pick(candidates, "exact", "2230.07.17")["reasons"] == ["War Declared"]
    assert pick(candidates, "exact", "2268.09.15")["reasons"] == ["The Stars Know War"]
    started = pick(candidates, "between", "2259.12.29", "2273.09.07")
    assert started["reasons"] == ["war started: Die Borg - Vulkan War"]
    ended = pick(candidates, "between", "2273.09.07", "2284.09.29")
    assert ended["reasons"] == ["war ended: Die Borg - Vulkan War"]
    assert len(material["timeline"]["events"]) == 23 and material["timeline"]["complete"]
    assert len(material["intervals"]) == 7
    assert len(build_findings(material["intervals"])) >= 7


def run_check(workspace, path, capsys):
    code = main(
        ["debrief", "check-epochs", "--workspace", str(workspace), "--epochs", str(path)]
        + ["--since", "all"]
    )
    return code, json.loads(capsys.readouterr().out)


@pytest.mark.saves
def test_a_reference_epochs_file_passes_and_a_border_at_2240_fails(
    reference_workspace, tmp_path, capsys
):
    good = [
        epoch("Early growth", "2200.01.01", "2230.07.17"),
        epoch("Between the wars", "2230.07.17", "2268.09.15", exact("2230.07.17", "War Declared")),
        epoch("The war", "2268.09.15", "2280.01.01", exact("2268.09.15", "The Stars Know War")),
        epoch("After", "2280.01.01", "2298.03.16", between("2273.09.07", "2284.09.29")),
    ]
    path = tmp_path / "epochs.json"
    path.write_text(json.dumps(good))
    code, out = run_check(reference_workspace, path, capsys)
    assert (code, out["errors"]) == (0, [])
    assert out["frame"] == {"from": "2200.01.01", "to": "2298.03.16", "request": "all"}

    bad = [
        epoch("Early", "2200.01.01", "2240.01.01"),
        epoch("Rest", "2240.01.01", "2298.03.16", exact("2240.01.01", "Anything")),
    ]
    path.write_text(json.dumps(bad))
    code, out = run_check(reference_workspace, path, capsys)
    assert code == 1
    assert out["errors"] == [
        "epoch 2 ('Rest'): no Timeline event or archived interval at 2240.01.01"
    ]


# --- the CLI on a synthetic archive ----------------------------------------------------------------------


def test_the_cli_reports_a_frame_that_cannot_be_resolved(tmp_path, capsys):
    (tmp_path / "epochs.json").write_text(json.dumps(GOOD))
    code = main(
        [
            "debrief",
            "check-epochs",
            "--workspace",
            str(tmp_path),
            "--epochs",
            str(tmp_path / "epochs.json"),
        ]
    )
    assert code == 1
    assert "needs two archived dates" in capsys.readouterr().err


def test_the_cli_refuses_an_unreadable_epochs_file(tmp_path):
    with pytest.raises(SystemExit, match="cannot read epochs"):
        main(
            [
                "debrief",
                "check-epochs",
                "--workspace",
                str(tmp_path),
                "--epochs",
                str(tmp_path / "none.json"),
            ]
        )


def _stub_frame(monkeypatch):
    """The CLI on a stand-in archive: the frame and the candidates are fixed."""
    from types import SimpleNamespace

    from admiralty.debrief import epochs as epochs_module
    from admiralty.debrief import frame as frame_module
    from admiralty.workspace import archive

    monkeypatch.setattr(archive, "Archive", lambda workspace: None)
    monkeypatch.setattr(
        frame_module, "load_campaign", lambda archive: SimpleNamespace(dates=[START, END])
    )
    monkeypatch.setattr(
        frame_module, "resolve_frame", lambda *a: SimpleNamespace(start=START, end=END, request="x")
    )
    monkeypatch.setattr(
        epochs_module,
        "candidates_for_frame",
        lambda loaded, frame: {"candidates": CANDIDATES, "timeline": {"events": []}},
    )


def _check_epochs_cli(tmp_path, epochs):
    (tmp_path / ".admiralty").mkdir(exist_ok=True)
    (tmp_path / "epochs.json").write_text(json.dumps(epochs))
    return main(
        [
            "debrief",
            "check-epochs",
            "--workspace",
            str(tmp_path),
            "--epochs",
            str(tmp_path / "epochs.json"),
        ]
    )


def test_accepted_epoch_titles_are_returned_and_count_as_evidence(tmp_path, capsys, monkeypatch):
    from admiralty.claims.check import check_answer
    from admiralty.claims.evidence import build_evidence, read_turn_log

    _stub_frame(monkeypatch)
    assert _check_epochs_cli(tmp_path, GOOD) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["epoch_titles"] == [e["title"] for e in GOOD]
    (entry,) = read_turn_log(tmp_path)
    assert entry["tool"] == "debrief_check_epochs"
    evidence = build_evidence([entry])
    title = GOOD[2]["title"]
    assert check_answer(f"## **{title}**", evidence).ok
    # an invented game name still stands out
    assert not check_answer("Die **Schlacht um Atlantis** begann.", evidence).ok


def test_a_refused_epoch_proposal_is_no_evidence(tmp_path, capsys, monkeypatch):
    from admiralty.claims.evidence import read_turn_log

    _stub_frame(monkeypatch)
    assert _check_epochs_cli(tmp_path, [GOOD[0], GOOD[2]]) == 1
    assert "epoch_titles" not in json.loads(capsys.readouterr().out)
    assert read_turn_log(tmp_path) == []


def test_events_are_placed_by_their_date_not_by_a_between_border():
    from admiralty.debrief.epochs import place_events

    epochs = [
        {"title": "Aufbau", "from": "2200.01.01", "to": "2259.12.29"},
        {"title": "Krieg", "from": "2259.12.29", "to": "2298.03.16"},
    ]
    events = [
        {"date": "2259.10.09", "event": "A World Reborn", "involves": ["Thrish IV"]},
        {"date": "2259.12.29", "event": "War Declared"},
        {"date": "2298.03.16", "event": "Last Day"},
    ]
    placed = place_events(epochs, events)
    assert placed[0]["events"] == ["2259.10.09 A World Reborn (Thrish IV)"]
    assert placed[1]["events"] == ["2259.12.29 War Declared", "2298.03.16 Last Day"]
