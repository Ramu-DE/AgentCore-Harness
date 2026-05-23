import os
import logging
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

from bedrock_agentcore.identity import requires_access_token

@requires_access_token(
    provider_name="workshop-gateway-oauth",
    scopes=[],
    auth_flow="M2M",
)
def _get_bearer_token_workshop_gateway(*, access_token: str):
    """Obtain OAuth access token via AgentCore Identity for workshop-gateway."""
    return access_token

def get_workshop_gateway_mcp_client() -> MCPClient | None:
    """Returns an MCP Client connected to the workshop-gateway gateway."""
    url = os.environ.get("AGENTCORE_GATEWAY_WORKSHOP_GATEWAY_URL")
    if not url:
        logger.warning("AGENTCORE_GATEWAY_WORKSHOP_GATEWAY_URL not set — workshop-gateway gateway tools unavailable")
        return None
    token = _get_bearer_token_workshop_gateway()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return MCPClient(lambda: streamablehttp_client(url, headers=headers))

def get_all_gateway_mcp_clients() -> list[MCPClient]:
    """Returns MCP clients for all configured gateways."""
    clients = []
    client = get_workshop_gateway_mcp_client()
    if client:
        clients.append(client)
    return clients
