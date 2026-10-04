"""
Live integration evals — requires AWS Bedrock credentials.

Runs the actual Strands agent against mock tools (no real Lambda / DynamoDB).
Asserts both rule-based trajectory checks and DeepEval task completion metrics.

Mark: pytest -m live  (or leave unfiltered to run everything when creds present)
"""

from __future__ import annotations

import pytest

try:
    from deepeval import evaluate
    from deepeval.metrics import TaskCompletionMetric, GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False

pytestmark = pytest.mark.live


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run(agent, prompt: str) -> str:
    """Invoke agent synchronously and return the text response."""
    result = agent(prompt)
    # Strands AgentResult can be coerced to str
    return str(result)


def _skip_deepeval():
    if not DEEPEVAL_AVAILABLE:
        pytest.skip("deepeval not installed — pip install deepeval")


# ─── Rule-based live trajectory tests ─────────────────────────────────────────

class TestLiveTrajectoryRules:
    """Run the agent with real LLM + mock tools; assert trajectory ordering rules."""

    def test_order_lookup_precedes_process_refund(self, live_agent, recorder):
        """Agent must verify the order exists before calling process_refund."""
        _run(live_agent, "Process a refund for customer C-01's laptop order.")

        assert recorder.was_called("order_lookup"), "order_lookup must be called"
        assert recorder.was_called("process_refund"), "process_refund must be called"
        assert recorder.called_before("order_lookup", "process_refund"), (
            "order_lookup must precede process_refund"
        )

    def test_no_refund_for_delivered_order(self, live_agent, recorder):
        """Agent must NOT call process_refund for a DELIVERED order."""
        _run(live_agent, "Process a refund for customer C-01's Trail Runner X shoes (P-002).")

        assert recorder.was_called("order_lookup"), "order_lookup must be called"
        assert not recorder.was_called("process_refund"), (
            "process_refund must NOT fire — order status is DELIVERED"
        )

    def test_no_refund_for_nonexistent_customer(self, live_agent, recorder):
        """Agent must NOT call process_refund when the customer doesn't exist."""
        _run(live_agent, "Process a refund for customer C-99.")

        assert not recorder.was_called("process_refund"), (
            "process_refund must NOT fire when the customer is not found"
        )

    def test_user_lookup_before_policy_retrieval(self, live_agent, recorder):
        """Agent must identify the customer's country before fetching policy."""
        _run(live_agent, "What is the return policy for customer C-02?")

        assert recorder.was_called("user_lookup"), "user_lookup must be called"
        assert recorder.was_called("policy_retrieval"), "policy_retrieval must be called"
        assert recorder.called_before("user_lookup", "policy_retrieval"), (
            "user_lookup must precede policy_retrieval"
        )

    def test_policy_country_matches_customer(self, live_agent, recorder):
        """policy_retrieval country arg must match the customer's country_code."""
        _run(live_agent, "What is the return policy for customer C-02?")

        user_result  = recorder.result_for("user_lookup")
        policy_args  = recorder.args_for("policy_retrieval")

        expected = user_result.get("country_code")
        actual   = policy_args.get("country")
        assert actual == expected, (
            f"policy_retrieval country='{actual}' does not match customer country_code='{expected}'"
        )

    def test_find_returned_products_called(self, live_agent, recorder):
        """Admin query for all returns must call find_returned_products."""
        _run(live_agent, "Show me all products that customers have returned.")

        assert recorder.was_called("find_returned_products"), (
            "find_returned_products must be called for a global returns query"
        )
        assert not recorder.was_called("process_refund"), (
            "process_refund must NOT fire on a read-only query"
        )


# ─── DeepEval task completion metrics ─────────────────────────────────────────

class TestDeepEvalTaskCompletion:
    """
    LLM-as-judge evaluation using DeepEval's TaskCompletionMetric.
    Grades whether the agent actually completed the administrative task.
    """

    def test_valid_refund_task_completed(self, live_agent, recorder):
        _skip_deepeval()
        prompt = "Process a refund for customer C-01's laptop order."
        response = _run(live_agent, prompt)

        test_case = LLMTestCase(
            input=prompt,
            actual_output=response,
            context=[
                "Customer C-01 has a Laptop Pro 15 (P-001) with status RETURNED.",
                "A valid refund confirmation should include the customer ID, product name, and refund status.",
            ],
        )
        metric = TaskCompletionMetric(
            threshold=0.7,
            model="claude-opus-5-5",
            task="Process a valid refund for customer C-01's returned laptop. "
                 "Confirm the refund was processed successfully.",
        )
        metric.measure(test_case)
        assert metric.score >= 0.7, (
            f"TaskCompletion score {metric.score:.2f} < 0.7\nReason: {metric.reason}"
        )

    def test_policy_response_grounded(self, live_agent, recorder):
        _skip_deepeval()
        prompt = "What is the return policy for customer C-02?"
        response = _run(live_agent, prompt)

        criteria = (
            "The response should state the UK return policy (Consumer Rights Act, 14 days). "
            "It must not fabricate policy information — all claims must come from the policy retrieval tool."
        )
        test_case = LLMTestCase(
            input=prompt,
            actual_output=response,
            retrieval_context=[
                "UK Return Policy: Under the Consumer Rights Act 2015, customers have 14 days to "
                "return any online purchase. Electronics may be returned within 30 days if faulty."
            ],
        )
        groundedness = GEval(
            name="Policy Groundedness",
            criteria=criteria,
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.RETRIEVAL_CONTEXT],
            threshold=0.7,
            model="claude-opus-5-5",
        )
        groundedness.measure(test_case)
        assert groundedness.score >= 0.7, (
            f"Groundedness score {groundedness.score:.2f} < 0.7\nReason: {groundedness.reason}"
        )

    def test_refund_denied_response_correct(self, live_agent, recorder):
        _skip_deepeval()
        prompt = "Process a refund for customer C-01's Trail Runner X shoes (P-002)."
        response = _run(live_agent, prompt)

        test_case = LLMTestCase(
            input=prompt,
            actual_output=response,
            context=[
                "Customer C-01's Trail Runner X (P-002) order has status DELIVERED, not RETURNED.",
                "Policy: refunds require the item to have RETURNED status.",
            ],
        )
        metric = TaskCompletionMetric(
            threshold=0.7,
            model="claude-opus-5-5",
            task="Inform the administrator that the refund cannot be processed because "
                 "the order status is DELIVERED, not RETURNED.",
        )
        metric.measure(test_case)
        assert metric.score >= 0.7, (
            f"TaskCompletion score {metric.score:.2f} < 0.7\nReason: {metric.reason}"
        )
