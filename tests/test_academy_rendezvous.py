"""The Rendezvous (M9, 20g): proposal, moving, and the answer for the newest save before, at and after it."""

from __future__ import annotations

import pytest

from admiralty.academy import predictions, rendezvous
from admiralty.player.mastery import Refused


def open_prediction(check_date, *, basis="foretold", state="open", id_="p001"):
    return {"id": id_, "check_date": check_date, "basis": basis, "state": state}


# --- proposal -------------------------------------------------------------------------------


def test_propose_without_predictions_is_two_years_ahead_at_a_month_start():
    proposal = rendezvous.propose("2288.05.17")
    assert proposal["date"] == "2290.06.01"
    assert proposal["save_name"] == "Academy 2290-06"
    assert proposal["checks"] == []


def test_propose_on_a_month_start_keeps_the_date():
    assert rendezvous.propose("2288.05.01")["date"] == "2290.05.01"


def test_propose_waits_for_the_latest_open_prediction():
    later = open_prediction("2293.03.10", id_="p002")
    proposal = rendezvous.propose("2288.05.01", [open_prediction("2290.01.01"), later])
    assert proposal["date"] == "2293.04.01"
    assert proposal["checks"] == ["p001", "p002"]


def test_propose_ignores_decided_and_hindsight_predictions():
    ignored = [
        open_prediction("2293.01.01", state="confirmed"),
        open_prediction("2293.01.01", basis="hindsight", id_="p002"),
    ]
    assert rendezvous.propose("2288.05.01", ignored)["date"] == "2290.05.01"


def test_propose_is_never_more_than_five_years_ahead():
    far = open_prediction("2293.05.01")  # exactly five years, no rounding room
    assert rendezvous.propose("2288.05.01", [far])["date"] == "2293.05.01"
    # rounding up to a month start would pass the cap, so the check date itself is used
    off_month = open_prediction("2293.05.15")
    assert rendezvous.propose("2288.05.17", [off_month])["date"] == "2293.05.15"
    assert rendezvous.propose("2288.05.17", [open_prediction("2293.05.17")])["date"] == "2293.05.17"


def test_propose_takes_another_horizon_and_refuses_one_beyond_five_years():
    assert rendezvous.propose("2288.05.01", years=1)["date"] == "2289.05.01"
    for years in (0, 5.1):
        with pytest.raises(Refused):
            rendezvous.propose("2288.05.01", years=years)


def test_save_name_carries_year_and_month():
    assert rendezvous.save_name("2290.01.15") == "Academy 2290-01"


# --- agreeing and moving --------------------------------------------------------------------


def test_set_stores_the_agreement_and_reports_unchecked_predictions(tmp_path):
    late = open_prediction("2292.01.01")
    agreed = rendezvous.set_rendezvous(
        tmp_path,
        "2290.01.01",
        today="2288.05.01",
        predictions=[late, open_prediction("2289.01.01", id_="p002")],
    )
    assert agreed["date"] == "2290.01.01" and agreed["save_name"] == "Academy 2290-01"
    assert agreed["unchecked"] == ["p001"] and agreed["moves"] == []
    assert rendezvous.load(tmp_path)["date"] == "2290.01.01"


def test_set_takes_the_save_name_the_player_prefers(tmp_path):
    agreed = rendezvous.set_rendezvous(
        tmp_path, "2290.01.01", today="2288.05.01", save_name_="Fleet check"
    )
    assert agreed["save_name"] == "Fleet check"


def test_moving_keeps_the_earlier_dates(tmp_path):
    rendezvous.set_rendezvous(tmp_path, "2290.01.01", today="2288.05.01")
    rendezvous.set_rendezvous(tmp_path, "2290.01.01", today="2288.06.01")  # same date: not a move
    moved = rendezvous.set_rendezvous(tmp_path, "2291.01.01", today="2289.02.01")
    assert moved["date"] == "2291.01.01"
    assert moved["moves"] == [
        {"date": "2290.01.01", "save_name": "Academy 2290-01", "moved_on": "2289.02.01"}
    ]
    assert rendezvous.load(tmp_path)["moves"] == moved["moves"]


@pytest.mark.parametrize("date", ["2288.05.01", "2288.04.01", "2293.05.02", "soon"])
def test_set_refuses_a_date_not_ahead_or_beyond_five_years(tmp_path, date):
    with pytest.raises(ValueError):
        rendezvous.set_rendezvous(tmp_path, date, today="2288.05.01")
    assert rendezvous.load(tmp_path) is None


def test_the_proposal_can_be_agreed_as_it_is(tmp_path):
    made = predictions.add(
        tmp_path,
        kind="war",
        sentence="The border holds.",
        made="2288.05.01",
        check_date="2291.02.10",
    )
    proposal = rendezvous.propose("2288.05.01", [made])
    agreed = rendezvous.set_rendezvous(
        tmp_path, proposal["date"], today="2288.05.01", predictions=[made]
    )
    assert agreed["date"] == "2291.03.01" and agreed["unchecked"] == []


# --- before, at, after ----------------------------------------------------------------------


def test_without_a_rendezvous_there_is_no_position(tmp_path):
    assert rendezvous.position(tmp_path, "2290.01.01") == {"position": "none"}


@pytest.fixture
def agreed(tmp_path):
    rendezvous.set_rendezvous(tmp_path, "2290.01.01", today="2288.05.01")
    return tmp_path


def test_a_newest_save_before_the_date_is_before_with_the_days_left(agreed):
    found = rendezvous.position(agreed, "2289.12.20")
    assert found["position"] == "before" and found["days_left"] == 11
    assert found["save_name"] == "Academy 2290-01"


def test_a_newest_save_on_the_date_or_shortly_after_is_at(agreed):
    assert rendezvous.position(agreed, "2290.01.01")["position"] == "at"
    assert rendezvous.position(agreed, "2290.01.31")["position"] == "at"


def test_a_newest_save_long_after_the_date_means_the_rendezvous_was_missed(agreed):
    found = rendezvous.position(agreed, "2290.02.03")
    assert found["position"] == "after" and found["missed"] is True
    assert found["days_late"] == 32 and found["date"] == "2290.01.01"


def test_damaged_agreement_is_an_error_not_a_silent_none(tmp_path):
    (tmp_path / "academy").mkdir()
    (tmp_path / "academy" / "rendezvous.json").write_text("{not json")
    with pytest.raises(Refused, match="damaged"):
        rendezvous.load(tmp_path)
