import time

import pytest

from hlidskjalf.extract.save import load_save


@pytest.mark.saves
def test_parses_late_save_in_under_3_seconds(late_save):
    start = time.perf_counter()
    save = load_save(late_save)
    elapsed = time.perf_counter() - start

    assert save.meta["version"] == "Cygnus v4.5.2"
    assert "planets" in save.gamestate and "country" in save.gamestate
    assert elapsed < 3.0, f"parsing took {elapsed:.2f} s"
