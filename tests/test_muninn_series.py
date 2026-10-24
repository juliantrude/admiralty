"""Muninn frame, series, intervals and Timeline merge: synthetic archives, then the reference Campaign."""

from __future__ import annotations

import os

import pytest
from conftest import SAVES_DIR, VULKAN, reference_save

from hlidskjalf.mcp.service import CampaignService
from hlidskjalf.muninn.frame import (
    FrameError,
    load_campaign,
    resolve_frame,
    years_between,
)
from hlidskjalf.muninn.series import (
    build_intervals,
    build_series,
    change,
    merge_timeline,
    series_values,
    timeline_in_frame,
)
from hlidskjalf.workspace.archive import Archive
from hlidskjalf.workspace.config import CampaignConfig

DATES = ["2200.01.01", "2220.04.26", "2245.01.23", "2259.12.29", "2298.03.11"]


def doc(date, *, planets=2, pops=100, military=1000, wars=(), timeline=(), total=None, **header):
    return {
        "schema": 1,
        "header": {
            "date": date,
            "campaign": "vulkan",
            "tracked_empire": {"country_id": 1, "name": "Die Borg", "player": "Anna"},
            **header,
        },
        "empire": {
            "military_power": military,
            "economy_power": 50,
            "tech_power": 40,
            "victory_rank": 6,
        },
        "resources": {
            "energy": {"label": "Energy Credits", "stockpile": 200.5, "net": -3.25},
            "alloys": {"label": "Alloys", "stockpile": 0, "net": 0},
        },
        "pops": {"total": pops, "unemployed": 4},
        "planets": [{"id": i, "name": f"P{i}", "system": "S", "pops": 10} for i in range(planets)],
        "naval_capacity": {"used": 10, "max": 20},
        "progression": {"traditions": ["A"], "ascension_perks": []},
        "military": {"wars": [{"name": n} for n in wars]},
        "timeline": list(timeline),
        "timeline_events_total": len(timeline) if total is None else total,
        "known_empires": [
            {"country_id": 0, "name": "Vulkan", "visible": {"origin": "x"}, "full": {"fleet": 85}}
        ],
    }


def store(tmp_path, *docs):
    archive = Archive(tmp_path)
    for index, d in enumerate(docs):
        archive.store(d, 100.0 + index)
    return archive


# --- frame ---------------------------------------------------------------------------------


def test_the_default_and_last_frame_are_the_two_newest_dates():
    for request in (None, "last"):
        frame = resolve_frame(DATES, request)
        assert (frame.start, frame.end, frame.request) == ("2259.12.29", "2298.03.11", "last")
        assert frame.dates == ["2259.12.29", "2298.03.11"]


def test_all_runs_from_the_first_to_the_last_date():
    frame = resolve_frame(DATES, "all")
    assert (frame.start, frame.end, frame.dates) == ("2200.01.01", "2298.03.11", DATES)


def test_since_starts_on_the_newest_archived_date_at_or_before_it():
    assert resolve_frame(DATES, "2250.06.01").start == "2245.01.23"  # inside a gap: back to data
    assert resolve_frame(DATES, "2245.01.23").start == "2245.01.23"  # exactly on a date
    assert resolve_frame(DATES, "2100.01.01").start == "2200.01.01"  # before everything
    frame = resolve_frame(DATES, "2250.06.01")
    assert frame.dates == ["2245.01.23", "2259.12.29", "2298.03.11"]
    assert frame.request == "since 2250.06.01"


def test_until_moves_the_end_to_an_archived_date_and_last_follows_it():
    frame = resolve_frame(DATES, None, "2250.01.01")
    assert (frame.start, frame.end) == ("2220.04.26", "2245.01.23")
    both = resolve_frame(DATES, "2210.01.01", "2260.01.01")
    assert (both.start, both.end) == ("2200.01.01", "2259.12.29")
    assert both.request == "since 2210.01.01 until 2260.01.01"
    assert resolve_frame(DATES, "all", "2245.01.23").dates == DATES[:3]


def test_fewer_than_two_dates_is_an_error_that_says_how_many():
    with pytest.raises(FrameError, match="holds none"):
        resolve_frame([])
    with pytest.raises(FrameError, match=r"only 2259\.12\.29.*read another save"):
        resolve_frame(["2259.12.29"], "all")


def test_a_request_that_leaves_one_date_or_none_is_an_error():
    with pytest.raises(FrameError, match="needs two archived dates"):
        resolve_frame(DATES, "2299.01.01")  # newest date alone
    with pytest.raises(FrameError, match="needs two archived dates"):
        resolve_frame(DATES, "all", "2201.01.01")
    with pytest.raises(FrameError, match="nothing is archived up to it"):
        resolve_frame(DATES, None, "2100.01.01")


def test_a_malformed_date_is_refused():
    for bad in ("2250-01-01", "yesterday", "2250.1.1"):
        with pytest.raises(FrameError, match="not an in-game date"):
            resolve_frame(DATES, bad)
    with pytest.raises(FrameError, match="not an in-game date"):
        resolve_frame(DATES, None, "soon")


def test_a_year_has_360_days():
    assert years_between("2200.01.01", "2201.01.01") == 1.0
    assert years_between("2200.01.01", "2298.03.11") == 98.19
    assert years_between("2200.01.01", "2200.01.01") == 0


# --- loading the archive ---------------------------------------------------------------------


def test_load_campaign_reads_by_header_date_and_lists_what_it_leaves_out(tmp_path):
    archive = store(tmp_path, doc("2220.04.26"), doc("2200.01.01"), doc("2259.12.29"))
    stray = doc("2230.01.01", campaign=None)
    stray["header"]["campaign"] = "other"
    archive.store(stray, 1.0)
    (archive.extracts / "2240.01.01.json.zst").write_bytes(b"not zstd")
    loaded = load_campaign(archive)
    assert loaded.dates == ["2200.01.01", "2220.04.26", "2259.12.29"]
    problems = "\n".join(loaded.problems)
    assert "2240.01.01" in problems and "cannot be read" in problems
    assert "2230.01.01: skipped" in problems and "another Campaign" in problems


def test_load_campaign_of_an_empty_archive(tmp_path):
    loaded = load_campaign(Archive(tmp_path))
    assert loaded.dates == [] and loaded.problems == []


# --- series and intervals ----------------------------------------------------------------------


def test_series_values_are_flat_and_use_the_display_name_labels():
    values = series_values(doc("2200.01.01", planets=3))
    assert values["planets"] == 3 and values["pops"] == 100 and values["unemployed"] == 4
    assert values["naval_capacity_used"] == 10 and values["naval_capacity_max"] == 20
    assert values["traditions"] == 1 and values["ascension_perks"] == 0
    assert values["wars_running"] == 0 and values["victory_rank"] == 6
    assert values["Energy Credits stockpile"] == 200.5 and values["Energy Credits net"] == -3.25
    assert values["Alloys net"] == 0
    assert "energy net" not in values  # the key is not a name


def test_a_value_the_extract_lacks_is_left_out():
    bare = {"header": {"date": "2200.01.01"}, "pops": {"total": 5}}
    assert series_values(bare) == {"pops": 5}


def test_known_empires_are_filtered_by_the_campaigns_knowledge():
    documents = [doc("2200.01.01")]
    fair = build_series(documents, god_mode=False)[0]["known_empires"][0]
    assert "full" not in fair and fair["visible"] == {"origin": "x"}
    god = build_series(documents, god_mode=True)[0]["known_empires"][0]
    assert god["full"] == {"fleet": 85}
    assert "full" in documents[0]["known_empires"][0]  # the archived document is untouched


def test_change_with_a_zero_start_has_no_percentage():
    assert change(0, 5) == {"from": 0, "to": 5, "change": 5}
    assert change(200, 250) == {"from": 200, "to": 250, "change": 50, "change_pct": 25}
    assert change(4, 3) == {"from": 4, "to": 3, "change": -1, "change_pct": -25}
    assert change(-10, -5)["change_pct"] == 50  # the loss shrank
    assert change(3, 4)["change_pct"] == 33.3


def test_intervals_hold_changes_gains_and_wars():
    first = doc("2200.01.01", planets=2, pops=100, military=1000, wars=("Old War",))
    second = doc("2220.04.26", planets=5, pops=250, military=800)
    second["progression"] = {"traditions": ["A", "B"], "ascension_perks": ["Perk"]}
    interval = build_intervals([first, second])[0]
    assert (interval["from"], interval["to"], interval["years"]) == (
        "2200.01.01",
        "2220.04.26",
        20.32,
    )
    assert interval["values"]["planets"] == {"from": 2, "to": 5, "change": 3, "change_pct": 150}
    assert interval["values"]["military_power"]["change_pct"] == -20
    assert interval["values"]["pops"]["change_pct"] == 150
    assert interval["values"]["Alloys net"] == {"from": 0, "to": 0, "change": 0}
    assert interval["planets_gained"] == ["P2", "P3", "P4"] and interval["planets_lost"] == []
    assert interval["traditions_adopted"] == ["B"] and interval["ascension_perks_taken"] == ["Perk"]
    assert interval["wars_started"] == [] and interval["wars_ended"] == ["Old War"]
    assert interval["values"]["wars_running"] == {
        "from": 1,
        "to": 0,
        "change": -1,
        "change_pct": -100,
    }


def test_intervals_one_per_neighbouring_pair_and_none_for_one_document():
    documents = [doc(d) for d in DATES[:4]]
    pairs = [(i["from"], i["to"]) for i in build_intervals(documents)]
    assert pairs == list(zip(DATES, DATES[1:4], strict=False))
    assert build_intervals(documents[:1]) == []


# --- Timeline ------------------------------------------------------------------------------------


def event(date, name, *involves):
    return {"date": date, "event": name, "involves": list(involves)}


def test_the_timeline_merges_the_slices_and_counts_what_no_extract_holds():
    oldest = event("2200.01.01", "Start", "Die Borg")
    middle = event("2230.07.17", "War Declared", "Die Borg", "Vulkan")
    newest = event("2259.10.09", "A World Reborn", "Die Borg")
    early = doc("2220.04.26", timeline=[oldest, middle], total=2)
    late = doc("2259.12.29", timeline=[middle, newest], total=4)  # the newest slice dropped one
    merged = merge_timeline([early, late])
    assert [e["event"] for e in merged["events"]] == ["Start", "War Declared", "A World Reborn"]
    assert merged["missing"] == 1 and merged["complete"] is False
    late["timeline_events_total"] = 3
    assert merge_timeline([early, late])["complete"] is True


def test_events_are_deduplicated_on_date_event_and_involves():
    same = event("2230.07.17", "New Colony", "Die Borg", "Menkar")
    other = event("2230.07.17", "New Colony", "Die Borg", "Thrish")  # same day, other planet
    merged = merge_timeline(
        [doc("2240.01.01", timeline=[same, other]), doc("2250.01.01", timeline=[same])]
    )
    assert len(merged["events"]) == 2


def test_a_planet_named_in_an_old_extract_and_a_bare_id_in_a_new_one_is_one_event():
    named = event("2242.12.01", "New Colony", "Die Borg", "Menkar Prime")
    bare = event("2242.12.01", "New Colony", "Die Borg", "6")
    other = event("2242.12.01", "New Colony", "Die Borg", "Thrish IV")
    for order in ([named, bare], [bare, named]):
        merged = merge_timeline(
            [doc("2250.01.01", timeline=[order[0]]), doc("2260.01.01", timeline=[order[1]])]
        )
        assert merged["events"] == [named]
    both = merge_timeline(
        [doc("2250.01.01", timeline=[named, other]), doc("2260.01.01", timeline=[bare])]
    )
    assert len(both["events"]) == 2  # two colonies the same day stay two events


def test_the_frame_timeline_includes_both_ends_and_counts_earlier_events():
    events = [event(d, "E") for d in ("2200.01.01", "2230.07.17", "2250.01.01", "2260.01.01")]
    inside = timeline_in_frame(events, "2230.07.17", "2250.01.01")
    assert [e["date"] for e in inside["events"]] == ["2230.07.17", "2250.01.01"]
    assert inside["before_frame"] == 1


def test_a_timeline_without_events_is_complete():
    assert merge_timeline([doc("2200.01.01")]) == {"events": [], "complete": True, "missing": 0}


# --- the reference Campaign ----------------------------------------------------------------------

SAVE_NAMES = [
    "2200.01.01", "2220.04.22", "2245.01.23", "2259.12.25",
    "2273.09.03", "2284.09.27", "2288.05.01", "2298.03.11",
]  # fmt: skip


@pytest.mark.saves
def test_the_eight_reference_dates_give_series_intervals_and_the_whole_timeline(tmp_path):
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
        link.unlink()  # Muninn reads the archive alone

    loaded = load_campaign(Archive(ws))
    assert loaded.problems == [] and len(loaded.dates) == 8
    assert loaded.dates[0] == "2200.01.01" and loaded.dates[-1].startswith("2298.")
    assert "2220.04.26" in loaded.dates  # header date, not the file name

    frame = resolve_frame(loaded.dates, "all")
    documents = [loaded.documents[d] for d in frame.dates]
    assert len(build_series(documents, god_mode=False)) == 8
    intervals = build_intervals(documents)
    assert len(intervals) == 7
    assert sum(i["years"] for i in intervals) == pytest.approx(
        years_between(frame.start, frame.end), abs=0.1
    )
    assert all("planets" in i["values"] and "Energy Credits net" in i["values"] for i in intervals)

    merged = merge_timeline(list(loaded.documents.values()))
    assert len(merged["events"]) == 23 and merged["complete"] is True
    assert any(e["date"] == "2230.07.17" for e in merged["events"])
    last = resolve_frame(loaded.dates)
    assert last.dates == loaded.dates[-2:]
