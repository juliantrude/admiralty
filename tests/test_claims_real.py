"""The Unverified Claim check on the reference mid-save (M7 verification): the real `planets` result
is the evidence, a true district count passes and a planted wrong one is blocked."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from conftest import SAVES_DIR, VULKAN, reference_save

from admiralty.claims.check import check_answer
from admiralty.claims.evidence import build_evidence, read_turn_log
from admiralty.mcp.service import CampaignService
from admiralty.workspace.config import CampaignConfig
from admiralty.workspace.turnlog import turn_log_path

pytestmark = pytest.mark.saves


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    reference_save(VULKAN, "2259.12.25.sav")
    workspace = tmp_path_factory.mktemp("workspace")
    (workspace / "campaign.yaml").write_text(
        f"save_dir: {SAVES_DIR / VULKAN}\nempire: Plexxi\nmode: consulting\nknowledge: fair_play\n"
    )
    result = CampaignService(CampaignConfig.load(workspace)).planets("2259.12.25")
    log = turn_log_path(workspace)
    log.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(UTC).isoformat(), "tool": "planets", "args": {}, "result": result}
    log.write_text(json.dumps(entry) + "\n")
    return build_evidence(read_turn_log(workspace), ())


def test_the_true_district_count_passes(evidence):
    answer = "**Unimatrix 1** hat 17 Distrikte, das Limit ist 17, 8 Pops sind arbeitslos."
    assert check_answer(answer, evidence).ok


def test_a_planted_wrong_district_count_is_blocked(evidence):
    answer = "**Unimatrix 1** hat 19 Distrikte, das Limit ist 17, 8 Pops sind arbeitslos."
    verdict = check_answer(answer, evidence)
    assert [u.claim.text for u in verdict.unverified] == ["19"]
