"""Acceptance: every benign benchmark task completes with KAVACH ON and nothing is intervened on."""

import pytest

from bench.cases import load_cases
from bench.runner import run_case

BENIGN = load_cases("benign")


def test_benign_suite_is_big_enough() -> None:
    assert len(BENIGN) >= 15


@pytest.mark.parametrize("case", BENIGN, ids=[c.id for c in BENIGN])
async def test_benign_case_passes_untouched(case) -> None:
    result = await run_case(case, enabled=True)
    assert result["tasks_completed"] == result["tasks_total"]
    assert result["interventions"] == []
    assert max(result["latencies_ms"]) < 10
