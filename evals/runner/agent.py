"""
Local eval runner — creates a Strands Agent wired to mock tools.

This bypasses the MCP gateway and AgentCore runtime so tests run without
any AWS service calls (except Bedrock for LLM inference).

Usage:
    from evals.runner.agent import build_eval_agent
    from evals.mocks.tools import TraceRecorder, set_recorder

    recorder = TraceRecorder()
    set_recorder(recorder)
    agent = build_eval_agent()
    result = agent("Process refund for customer C-01.")
    assert recorder.called_before("order_lookup", "process_refund")
"""

from __future__ import annotations

import sys
import pathlib

# Allow importing agent app modules from the CustomerAssistantAgent directory
_AGENT_DIR = pathlib.Path(__file__).parents[2] / "AgentCoreProject" / "app" / "CustomerAssistantAgent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from strands import Agent
from strands.models.bedrock import BedrockModel

from evals.mocks.tools import ALL_MOCK_TOOLS

# System prompt mirrors CustomerAssistantAgent/main.py but uses unprefixed tool
# names (no MCP gateway prefix) since tools are injected directly.
EVAL_SYSTEM_PROMPT = """
You are the Returns & Refunds Assistant. You help administrators manage customer
returns and refunds efficiently.

The user is an administrator with access to customer data, order history, and
return policies. You assist them in:
- Looking up customer orders and account information
- Checking return eligibility for specific orders
- Calculating refund amounts based on policy rules
- Answering questions about return and refund policies

## Available Tools

You have access to the following tools. ALWAYS use these tools to answer
questions — do NOT make up information:

1. order_lookup       — Look up all orders for a customer by customer_id (e.g. "C-01").
2. user_lookup        — Look up customer details (name, country) by customer_id.
3. product_lookup     — Look up product details (name, category, provider) by product_id.
4. find_returned_products — Find all orders with RETURNED status across all customers.
5. process_refund     — Process a refund given customer_id and product_id.
6. policy_retrieval   — Retrieve return/refund policy. Accepts a query string and
                        optional country code (e.g. "US", "GB", "MX").

## Guidelines

- ALWAYS use tools to look up real data. Never guess order or customer information.
- Use order_lookup first before calling process_refund.
- Use user_lookup to determine the customer's country before calling policy_retrieval
  with a country filter.
- Confirm order status before processing a refund — do not refund DELIVERED or
  CANCELLED orders.
- Be concise and cite tool results in your response.
"""

MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"


def build_eval_agent() -> Agent:
    """Create a Strands Agent with mock tools for local eval runs."""
    model = BedrockModel(model_id=MODEL_ID)
    return Agent(
        model=model,
        system_prompt=EVAL_SYSTEM_PROMPT,
        tools=ALL_MOCK_TOOLS,
    )
