"""
Offline trajectory tests — no LLM required.

Each test case loads its recorded_trajectory from the dataset JSONL,
replays it through the mock tools (producing realistic results), and then
asserts the trajectory rules. These run on every commit in under a second.

Two extra classes cover trajectory violation detection: verifying that the
rule-checker itself catches bad sequences before they reach production.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.mocks.tools import TraceRecorder, set_recorder

# ─── Load dataset ─────────────────────────────────────────────────────────────

_DATASET_FILE = Path(__file__).parent / "dataset" / "returns_refunds.jsonl"
DATASET: list[dict] = [
    json.loads(line)
    for line in _DATASET_FILE.read_text().splitlines()
    if line.strip()
]
IDS = [ex["id"] for ex in DATASET]


def _build_recorder(example: dict) -> TraceRecorder:
    """Replay the example's recorded_trajectory and return the populated recorder."""
    rec = TraceRecorder()
    set_recorder(rec)
    rec.replay(example["recorded_trajectory"])
    set_recorder(None)
    return rec


# ─── Parametrised rule checks ─────────────────────────────────────────────────

class TestMustCall:
    """Every tool listed in rules.must_call must appear in the trajectory."""

    @pytest.mark.parametrize("example", DATASET, ids=IDS)
    def test_required_tools_present(self, example: dict) -> None:
        rec = _build_recorder(example)
        for tool_name in example["rules"]["must_call"]:
            assert rec.was_called(tool_name), (
                f"[{example['id']}] '{tool_name}' was not called.\n"
                f"  Trajectory: {rec.names()}"
            )


class TestMustNotCall:
    """No tool listed in rules.must_not_call may appear in the trajectory."""

    @pytest.mark.parametrize("example", DATASET, ids=IDS)
    def test_forbidden_tools_absent(self, example: dict) -> None:
        rec = _build_recorder(example)
        for tool_name in example["rules"]["must_not_call"]:
            assert not rec.was_called(tool_name), (
                f"[{example['id']}] '{tool_name}' should NOT have been called.\n"
                f"  Trajectory: {rec.names()}"
            )


class TestOrderBefore:
    """For each [first, second] pair in rules.order_before, first must precede second."""

    @pytest.mark.parametrize("example", DATASET, ids=IDS)
    def test_tool_ordering(self, example: dict) -> None:
        rec = _build_recorder(example)
        for first, second in example["rules"]["order_before"]:
            assert rec.called_before(first, second), (
                f"[{example['id']}] '{first}' must be called before '{second}'.\n"
                f"  Trajectory: {rec.names()}"
            )


# ─── Violation detection tests ────────────────────────────────────────────────
# These verify that the rule-checker CATCHES bad trajectories.
# A bad trajectory is one a broken or misconfigured agent might produce.

class TestViolationDetection:
    """
    The rule-checker must flag bad trajectories — not silently pass them.
    These tests assert the NEGATIVE: the rule should evaluate to False.
    """

    def test_process_refund_without_order_lookup(self) -> None:
        """Refund called with no prior order lookup — trajectory is invalid."""
        rec = TraceRecorder()
        set_recorder(rec)
        from evals.mocks.tools import process_refund
        process_refund(customer_id="C-01", product_id="P-001")
        set_recorder(None)

        assert rec.was_called("process_refund"), "process_refund should be recorded"
        assert not rec.was_called("order_lookup"), "order_lookup was not called — that's the violation"
        # The ordering rule must FAIL (first=-1 means order_lookup missing)
        assert not rec.called_before("order_lookup", "process_refund"), (
            "called_before should return False when order_lookup is absent"
        )

    def test_policy_retrieval_without_user_lookup(self) -> None:
        """Policy retrieved without knowing the customer's country first."""
        rec = TraceRecorder()
        set_recorder(rec)
        from evals.mocks.tools import policy_retrieval
        policy_retrieval(query="return policy", country="US")
        set_recorder(None)

        assert not rec.was_called("user_lookup"), "user_lookup was skipped — that's the violation"
        assert not rec.called_before("user_lookup", "policy_retrieval"), (
            "called_before should return False when user_lookup is absent"
        )

    def test_process_refund_before_order_lookup(self) -> None:
        """Refund fires first, then order_lookup — ordering is inverted."""
        rec = TraceRecorder()
        set_recorder(rec)
        from evals.mocks.tools import process_refund, order_lookup
        process_refund(customer_id="C-01", product_id="P-001")
        order_lookup(customer_id="C-01")
        set_recorder(None)

        assert rec.was_called("process_refund")
        assert rec.was_called("order_lookup")
        assert not rec.called_before("order_lookup", "process_refund"), (
            "called_before('order_lookup', 'process_refund') must be False when order is inverted"
        )


# ─── Policy country-matching rule ─────────────────────────────────────────────

class TestPolicyCountryMatch:
    """
    When policy_retrieval is called for a customer, the country arg must match
    the customer's country_code from user_lookup.
    """

    @pytest.mark.parametrize("example", [ex for ex in DATASET if "policy_retrieval" in ex["rules"]["must_call"]], ids=[ex["id"] for ex in DATASET if "policy_retrieval" in ex["rules"]["must_call"]])
    def test_policy_country_matches_customer_country(self, example: dict) -> None:
        rec = _build_recorder(example)

        user_result = rec.result_for("user_lookup")
        policy_args = rec.args_for("policy_retrieval")

        if not user_result or not policy_args:
            pytest.skip("user_lookup or policy_retrieval not in this trajectory")

        expected_country = user_result.get("country_code")
        actual_country   = policy_args.get("country")

        assert actual_country == expected_country, (
            f"[{example['id']}] policy_retrieval country='{actual_country}' does not match "
            f"customer country_code='{expected_country}'"
        )
