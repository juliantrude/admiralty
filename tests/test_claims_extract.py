"""Unverified Claim check, first half (M7): number normalisation and what counts as a claim.

Pure tests, no saves. Matching against tool results is `test_claims_check.py`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from hlidskjalf.claims.extract import Claim, extract_claims
from hlidskjalf.claims.normalise import (
    Reading,
    apply_suffix,
    name_forms,
    normalise_name,
    read_tokens,
    to_decimal,
)


def readings(token: str) -> list[tuple[str, str]]:
    """(value, step) of every reading of a token that is one number."""
    (entry,) = read_tokens(token)
    return [(str(r.value), str(r.step)) for r in entry[2]]


def numbers(answer: str) -> list[Claim]:
    return [c for c in extract_claims(answer) if c.kind == "number"]


def values(answer: str) -> list[str]:
    """The first reading's value of every number claim, as text."""
    return [str(c.readings[0].value) for c in numbers(answer)]


def names(answer: str) -> list[str]:
    return [c.text for c in extract_claims(answer) if c.kind == "name"]


# --- normalisation -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("2794", [("2794", "1")]),
        ("2794.45", [("2794.45", "0.01")]),
        ("2794,45", [("2794.45", "0.01")]),
        ("2,794.45", [("2794.45", "0.01")]),
        ("2.794,45", [("2794.45", "0.01")]),
        ("1.234.567", [("1234567", "1")]),
        ("1,234,567", [("1234567", "1")]),
        ("0.250", [("0.250", "0.001")]),
        ("12345.678", [("12345.678", "0.001")]),
        ("7.4", [("7.4", "0.1")]),
        ("7,4", [("7.4", "0.1")]),
        ("1.50", [("1.50", "0.01")]),
    ],
)
def test_separator_readings(token, expected):
    assert readings(token) == expected


@pytest.mark.parametrize("token", ["2.794", "2,794", "999.999", "1,000"])
def test_one_separator_and_three_digits_is_read_both_ways(token):
    thousands, decimal = readings(token)
    assert thousands[1] == "1"
    assert decimal[1] == "0.001"
    assert Decimal(thousands[0]) == Decimal(decimal[0]) * 1000


def test_the_ambiguous_token_covers_either_reading():
    thousands, decimal = read_tokens("2.794")[0][2]
    assert thousands.covers(2794) and not thousands.covers(2.794)
    assert decimal.covers(2.794) and not decimal.covers(2794)


@pytest.mark.parametrize("token", ["4.5.2", "1.2.3", "2259.12.25", "10.5.2"])
def test_version_and_date_shaped_tokens_are_no_number(token):
    assert read_tokens(token) == []


def test_a_token_that_is_several_numbers_is_split():
    assert [(a, b, [str(r.value) for r in rs]) for a, b, rs in read_tokens("1,2,3")] == [
        (0, 1, ["1"]),
        (2, 3, ["2"]),
        (4, 5, ["3"]),
    ]


def test_the_magnitude_suffix_scales_value_and_precision():
    (reading,) = apply_suffix(read_tokens("7.4")[0][2], "k")
    assert (reading.value, reading.step) == (Decimal(7400), Decimal(100))
    (million,) = apply_suffix(read_tokens("1.2")[0][2], "M")
    assert (million.value, million.step) == (Decimal(1_200_000), Decimal(100_000))
    unchanged = read_tokens("7.4")[0][2]
    assert apply_suffix(unchanged, "%") == unchanged


@pytest.mark.parametrize(
    ("data", "covered"),
    [(7349.99, False), (7350, True), (7400, True), (7449.99, True), (7450, False)],
)
def test_precision_rounding_boundaries(data, covered):
    (reading,) = apply_suffix(read_tokens("7.4")[0][2], "k")
    assert reading.covers(data) is covered


def test_a_claim_covers_data_at_its_own_precision_only():
    (whole,) = read_tokens("2794")[0][2]
    (cents,) = read_tokens("2794.45")[0][2]
    assert whole.covers(2794.45)
    assert cents.covers(2794.45) and cents.covers(2794.449) and cents.covers(2794.454)
    assert not cents.covers(2794.4) and not cents.covers(2794.5)


def test_decimal_conversion_refuses_what_is_no_number():
    assert to_decimal(True) is None
    assert to_decimal(float("nan")) is None
    assert to_decimal(float("inf")) is None
    assert to_decimal(0.1) == Decimal("0.1")
    assert Reading(Decimal(5), Decimal(1)).covers(Decimal("5.4"))


@pytest.mark.parametrize(
    ("written", "key"),
    [
        ("**Naval Logistics Office**", "naval logistics office"),
        ("  `unity.more`: ", "unity.more"),
        ("„Supremacy“", "supremacy"),
        ("Fleet   Logistics Corps", "fleet logistics corps"),
    ],
)
def test_name_normalisation(written, key):
    assert normalise_name(written) == key


def test_name_forms_toggle_a_plural_s_only():
    assert {"anchorage", "anchorages"} <= name_forms("Anchorages")
    assert {"anchorage", "anchorages"} <= name_forms("Anchorage")
    assert "ga" not in name_forms("gas")  # too short to cut
    assert name_forms("Supremacy") == {"supremacy", "supremacys"}


# --- numbers in text ---------------------------------------------------------------------------


def test_every_spelling_is_one_claim_with_its_text_sign_and_percent():
    answer = (
        "Wir haben 2794.45 Energie, 2,794.45, 2.794,45, 7.4k, 7,4 k, 1.2M, -18, +5, 15 % und 15%."
    )
    claims = numbers(answer)
    assert [c.text for c in claims] == [
        "2794.45",
        "2,794.45",
        "2.794,45",
        "7.4k",
        "7,4 k",
        "1.2M",
        "-18",
        "+5",
        "15 %",
        "15%",
    ]
    assert [c.sign for c in claims] == [
        "",
        "",
        "",
        "",
        "",
        "",
        "-",
        "+",
        "",
        "",
    ]
    assert [c.percent for c in claims] == [False] * 8 + [True, True]
    assert str(claims[3].readings[0].value) == "7400.0"
    assert str(claims[3].readings[0].step) == "100.0"


def test_a_sign_needs_a_space_or_bracket_before_it():
    claims = numbers("Von 5-10 Schiffen, (-3) Unity, Tier-2, 7 - 3.")
    assert [(c.text, c.sign) for c in claims] == [
        ("5", ""),
        ("10", ""),
        ("-3", "-"),
        ("2", ""),
        ("7", ""),
        ("3", ""),
    ]


def test_a_magnitude_letter_must_end_the_word():
    assert [c.text for c in numbers("3 Kolonien, 5 Mining-Distrikte, 3 km, 4 k.")] == [
        "3",
        "5",
        "3",
        "4 k",
    ]


def test_the_sentence_of_each_claim_is_kept():
    claims = numbers("Die Flotte hat 20 Schiffe. Das Limit liegt bei 2.794 Punkten! Ende")
    assert [c.sentence for c in claims] == [
        "Die Flotte hat 20 Schiffe.",
        "Das Limit liegt bei 2.794 Punkten!",
    ]


def test_a_decimal_is_not_cut_into_sentences():
    (claim,) = numbers("Das sind 2.794 Punkte")
    assert claim.sentence == "Das sind 2.794 Punkte"


# --- what is not a claim -----------------------------------------------------------------------


def test_list_numbering_and_heading_numbers_are_no_claims():
    answer = "## 3. Strategie\n1. Erstens 20 Schiffe\n2) Zweitens\n- 4. Punkt mit 6\n### 2 Dinge"
    assert values(answer) == ["20", "6"]


def test_a_number_at_the_start_of_a_line_that_is_no_numbering_is_a_claim():
    assert values("2794 Energie\n-18 Unity") == ["2794", "18"]


def test_numbers_in_code_spans_and_fences_are_no_claims_but_a_bare_number_span_is():
    answer = (
        "Aufruf `uv run foo --port 8080`, Datei `m4.yaml`, Id `x.12`, Wert `2794`.\n"
        "```\nenergy 99999\n```\n"
        "Danach 12."
    )
    assert values(answer) == ["2794", "12"]


def test_link_targets_urls_and_versions_are_no_claims():
    answer = "[Hilfe 5](http://example.com/12/34) und https://x.y/99 und Version 4.5.2 und v1.2.3."
    assert values(answer) == ["5"]


def test_digits_glued_to_letters_are_no_claims():
    assert values("mk2, tier_2, 10th, 2x, A1, 3D") == []


def test_bare_years_are_exempt_and_in_game_dates_are_date_claims():
    answer = "Im Jahr 2250 und am 2259.12.25 hatten wir 2199 und 2501 Punkte."
    assert values(answer) == ["2199", "2501"]
    (date,) = [c for c in extract_claims(answer) if c.kind == "date"]
    assert date.text == date.key == "2259.12.25"
    assert date.sentence == answer


def test_a_year_with_a_percent_sign_is_still_a_claim():
    assert values("2250% mehr") == ["2250"]


def test_blockquote_lines_are_flagged_quoted():
    claims = numbers("> Regel: ab 20% Überschuss\nAntwort: 30 Schiffe")
    assert [(c.text, c.quoted) for c in claims] == [("20%", True), ("30", False)]


# --- units -------------------------------------------------------------------------------------


def test_a_list_item_a_table_row_and_a_paragraph_are_each_one_unit():
    answer = (
        "Absatz mit 1 und\nFortsetzung mit 2.\n\n"
        "- Punkt mit 3\n  weiter mit 4\n- Zweiter mit 5\n\n"
        "| Name | Wert |\n|---|---|\n| A | 6 |\n| B | 7 |\n\n"
        "## Titel mit 8\nDanach 9"
    )
    by_value = {c.readings[0].value: c.unit for c in numbers(answer)}
    units = [by_value[Decimal(i)] for i in range(1, 10)]
    assert units[0] == units[1]
    assert units[2] == units[3] != units[4]
    assert len({units[0], units[2], units[4], units[5], units[6], units[7], units[8]}) == 7


# --- names -------------------------------------------------------------------------------------


def test_bold_code_and_quoted_spans_are_names():
    answer = (
        'Baue das **Naval Logistics Office**, nutze `unity.more` und die Tradition "Supremacy",'
        " dazu „Fleet Logistics Corps“ und «Anchorage»."
    )
    claims = [c for c in extract_claims(answer) if c.kind == "name"]
    assert [(c.text, c.via) for c in claims] == [
        ("Naval Logistics Office", "bold"),
        ("unity.more", "code"),
        ("Supremacy", "quote"),
        ("Fleet Logistics Corps", "quote"),
        ("Anchorage", "quote"),
    ]
    assert claims[0].key == "naval logistics office"
    assert claims[0].sentence == answer


def test_whole_line_bold_is_a_label_not_a_name():
    answer = "**Strategie**\n## **Ausblick**\n**Fazit:**\n- **Supremacy** hilft\nDie **Supremacy**."
    assert names(answer) == ["Supremacy", "Supremacy"]


def test_a_single_lowercase_word_is_no_name():
    assert names("Das ist **wichtig**, `energy`, „gut“ und **Tier 2**.") == ["Tier 2"]


def test_capitalised_german_nouns_are_no_names():
    answer = (
        "Die Flotte braucht mehr Energie, weil der Unterhalt der Schiffe die Einnahmen "
        "übersteigt und die Kolonien zu wenig Arbeiter haben."
    )
    assert names(answer) == []


def test_a_long_quote_is_prose_and_a_command_or_path_is_no_name():
    answer = (
        '"Wenn du eine Flotte hast die zu groß ist dann baue mehr Docks bitte" sagte er. '
        "Nutze `uv run hlidskjalf setup check`, `docs/plans/M7.md`, `campaign.yaml`."
    )
    assert names(answer) == []


def test_a_bold_number_is_a_number_not_a_name():
    claims = extract_claims("Es sind **12** Schiffe.")
    assert [c.kind for c in claims] == ["number"]


def test_a_bold_label_with_its_colon_inside_is_no_name_but_a_name_before_a_colon_is():
    answer = "- **Gesperrt:** weil die Unity fehlt\n- **Anchorage**: gibt Kapazität"
    assert names(answer) == ["Anchorage"]


def test_the_bold_lead_of_a_line_that_introduces_a_list_is_a_label():
    answer = (
        "- **Nicht mit Zahlen geprüft** (bitte im Spiel ansehen):\n- ob **Anchorage** frei ist:"
    )
    assert names(answer) == ["Anchorage"]


def test_a_bold_figure_with_its_unit_is_no_name():
    claims = extract_claims(
        "Das Netto ist **−130.92 Energy Credits pro Monat**, also **12 Schiffe**."
    )
    assert [c.kind for c in claims] == ["number", "number"]


def test_markup_inside_a_name_is_stripped_and_duplicates_collapse():
    claims = [c for c in extract_claims("**Naval Logistics Office**: ok `Naval Logistics Office`")]
    assert [(c.kind, c.text) for c in claims] == [("name", "Naval Logistics Office")]


def test_table_cells_of_a_name_column_are_names():
    answer = (
        "| Name | Kosten | Wirkung |\n|---|---|---|\n"
        "| Anchorage | 150 | Kapazität |\n| **Naval Logistics Office** | 200 | mehr |\n"
        "| — | 5 | nichts |\n"
        "\n| Spalte | Wert |\n|---|---|\n| Nicht Name | 4 |\n"
    )
    assert names(answer) == ["Anchorage", "Naval Logistics Office"]


def test_a_table_without_a_name_column_has_no_names_but_keeps_its_numbers():
    answer = "| Dekade | Wert |\n|---|---|\n| Alpha Beta | 4 |\n"
    claims = extract_claims(answer)
    assert [c.kind for c in claims] == ["number"]
    assert claims[0].sentence == "| Alpha Beta | 4 |"


def test_a_number_inside_a_marked_name_knows_its_name():
    claims = extract_claims("Baue **Hangar 3** und „Tier 2“ mit 5 Schiffen.")
    inside = {c.text: c.within_name for c in claims if c.kind == "number"}
    assert inside == {"3": "hangar 3", "2": "tier 2", "5": None}


def test_a_number_in_a_code_span_name_is_not_extracted_at_all():
    assert values("Nutze `Hangar 3` heute.") == []
    assert names("Nutze `Hangar 3` heute.") == ["Hangar 3"]


def test_the_empty_and_the_number_free_answer_have_no_claims():
    assert extract_claims("") == []
    assert extract_claims("Mehr Schiffe wären gut.\n\nGruß") == []
