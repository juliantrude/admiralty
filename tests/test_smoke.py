import time

import pytest
from conftest import budget

from hlidskjalf.extract.save import load_save


@pytest.mark.saves
def test_parses_late_save_in_under_3_seconds(late_save):
    start = time.process_time()  # CPU time: robust against other load on the machine
    save = load_save(late_save)
    elapsed = time.process_time() - start

    assert save.meta["version"] == "Cygnus v4.5.2"
    assert "planets" in save.gamestate and "country" in save.gamestate
    assert elapsed < budget(3.0), f"parsing took {elapsed:.2f} s"
