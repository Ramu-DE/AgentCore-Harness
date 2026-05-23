"""
CustomerAssistantAgent — Returns & Refunds Assistant.

Connects to the AgentCore Gateway via MCP to access:
- order_lookup, user_lookup, product_lookup (data_lookup Lambda)
- policy_retrieval (policy_retrieval Lambda)

Keeps the current_time tool and AgentCore Memory integration intact.
"""

import os
import uuid

from strands import Agent
from strands_tools import current_time
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from model.load import load_model
from mcp_client.client import get_streamable_http_mcp_client

app = BedrockAgentCoreApp()
log = app.logger

# Gateway MCP client — discovers tools (order_lookup, user_lookup, product_lookup, policy_retrieval)
mcp_clients = [get_streamable_http_mcp_client()]

DEFAULT_SYSTEM_PROMPT = """
You are the Returns & Refunds Assistant. You help administrators manage customer
returns and refunds efficiently.

The user is an administrator with access to customer data, order history, and
return policies. You assist them in:
- Looking up customer orders and account information
- Checking return eligibility for specific orders
- Calculating refund amounts based on policy rules
- Answering questions about return and refund policies on behalf of customers

## Available Tools

You have access to the following tools via the MCP gateway. ALWAYS use these
tools to answer questions — do NOT make up information or search the web:

1. **data-lookup___order_lookup** — Look up all orders for a customer by customer_id (e.g. "C-01").
2. **data-lookup___user_lookup** — Look up customer details (name, country) by customer_id.
3. **data-lookup___product_lookup** — Look up product details (name, category, provider) by product_id.
4. **policy-retrieval___policy_retrieval** — Retrieve return/refund policy information from the knowledge base. Accepts a natural language query and an optional country code (e.g. "IN", "US").

## Guidelines

- ALWAYS use the tools above to look up real data. Never guess or fabricate order/customer/policy information.
- When asked about orders, use order_lookup first, then enrich with user_lookup and product_lookup as needed.
- When asked about return policies, use policy_retrieval with the relevant query and country.
- Be helpful and concise in your responses.
- Always confirm order details and customer information before processing any
  return or refund action.
- Cite the relevant policy when explaining eligibility decisions.
"""

# ─── Tool Setup ──────────────────────────────────────────────────────────────

# Local tools — current_time is kept for time-related queries
tools = [current_time]

# Gateway tools are discovered dynamically via the MCP client
for mcp_client in mcp_clients:
    if mcp_client:
        tools.append(mcp_client)

# ─── Memory Configuration ────────────────────────────────────────────────────

# Read the memory ID from environment — literal value set in agentcore.json envVars
MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "AgentCoreProject_CustomerAssistantMemory-t0PQ1ICcGo")

# Default actor ID for the administrator user
ACTOR_ID = "administrator"

def create_agent(session_id: str | None = None) -> Agent:
    """Create a new agent instance with a fresh AgentCore Memory session.

    Each invocation gets its own session to avoid cross-conversation contamination.
    Pass an explicit session_id to resume a prior conversation.
    """
    # Generate a unique session ID if not provided — ensures a clean slate per call
    resolved_session_id = session_id or str(uuid.uuid4())

    # Configure AgentCore Memory — short-term memory for conversation persistence
    agentcore_memory_config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        session_id=resolved_session_id,
        actor_id=ACTOR_ID,
        # Retrieval config uses the default namespace for STM
        retrieval_config={
            f"/users/{ACTOR_ID}/preference/": RetrievalConfig(
                top_k=5,
                relevance_score=0.3,
            ),
        },
    )

    # Create session manager with us-west-2 region
    session_manager = AgentCoreMemorySessionManager(
        agentcore_memory_config=agentcore_memory_config,
        region_name="us-west-2",
    )

    return Agent(
        model=load_model(),
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tools=tools,
        session_manager=session_manager,
    )


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")

    # Use session_id from payload if provided, otherwise generate a fresh one
    session_id = payload.get("session_id")
    agent = create_agent(session_id=session_id)

    # Execute and format response
    stream = agent.stream_async(payload.get("prompt"))

    async for event in stream:
        # Handle Text parts of the response
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
