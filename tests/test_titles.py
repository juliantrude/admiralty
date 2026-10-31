"""The wording rules for graph titles (docs/plans/titles.md)."""

from admiralty.graph.mechanics import MechanicsGraph
from admiralty.graph.titles import lint, title_problems


def test_the_curated_graph_follows_the_wording_rules():
    assert lint(MechanicsGraph.load()) == []


def test_digits_are_reported_in_every_kind():
    for kind in ("goal", "cause", "remedy", "obstacle"):
        found = title_problems(kind, "Staff 2 jobs", "Staff 2 jobs, may")
        assert any("digits" in p for p in found), kind


def test_goal_and_remedy_are_limited_to_five_words():
    assert title_problems("goal", "More alloy income") == []
    assert any(
        "7 words" in p for p in title_problems("goal", "More alloy income for every single planet")
    )
    assert title_problems("remedy", "Staff more Metallurgist jobs") == []
    assert any(
        "6 words" in p for p in title_problems("remedy", "Staff more Metallurgist jobs on planets")
    )


def test_a_remedy_starts_with_an_imperative_verb():
    assert any("imperative" in p for p in title_problems("remedy", "More foundry zones"))


def test_a_cause_is_a_short_state():
    assert title_problems("cause", "Few staffed Metallurgist jobs") == []
    assert title_problems("cause", "Too few jobs that give out all the amenities pops use") != []


def test_an_obstacle_has_an_uncertain_title_with_may():
    assert title_problems("obstacle", "No free slot", "There may be no free slot") == []
    assert any("needs an uncertain_title" in p for p in title_problems("obstacle", "No free slot"))
    assert any(
        "'may'" in p for p in title_problems("obstacle", "No free slot", "There is no free slot")
    )
    assert any(
        "states" in p for p in title_problems("obstacle", "There may be no slot", "It may be")
    )


def test_the_review_page_is_current():
    """Titles changed? Run `uv run python tools/titles_review.py` to refresh docs/plans/titles-review.html."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "tools" / "titles_review.py"
    spec = importlib.util.spec_from_file_location("titles_review", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PAGE.read_text(encoding="utf-8") == module.build()
