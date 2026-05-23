"""
MCP client for connecting to the AgentCore Gateway.

Handles OAuth token management:
- Obtains JWT access tokens from Cognito using client_credentials grant
- Caches tokens and auto-refreshes before expiry
- Passes Bearer token in Authorization header for gateway calls
"""

import os
import time
import base64
import logging
import requests
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# Token cache — module-level singleton
_token_cache: dict = {
    "access_token": None,
    "expires_at": 0,
}


def _get_access_token() -> str:
    """
    Obtain a JWT access token from Cognito using client_credentials grant.
    Caches the token and refreshes it 60 seconds before expiry.
    """
    # Return cached token if still valid (with 60s buffer)
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    # Read OAuth credentials from environment
    client_id = os.environ["GATEWAY_CLIENT_ID"]
    client_secret = os.environ["GATEWAY_CLIENT_SECRET"]
    token_endpoint = os.environ["GATEWAY_TOKEN_ENDPOINT"]
    scope = os.environ["GATEWAY_SCOPE"]

    # Encode client credentials for Basic auth header
    auth_string = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    # Request a new token
    response = requests.post(
        token_endpoint,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_string}",
        },
        data={
            "grant_type": "client_credentials",
            "scope": scope,
        },
        timeout=10,
    )
    response.raise_for_status()

    token_data = response.json()
    _token_cache["access_token"] = token_data["access_token"]
    _token_cache["expires_at"] = time.time() + token_data.get("expires_in", 3600)

    logger.info("Obtained new gateway access token (expires in %ds)", token_data.get("expires_in", 3600))
    return _token_cache["access_token"]


def _create_gateway_transport():
    """
    Create a Streamable HTTP transport for the AgentCore Gateway.
    Injects the OAuth Bearer token into the Authorization header.
    """
    gateway_url = os.environ["GATEWAY_URL"]
    access_token = _get_access_token()

    return streamablehttp_client(
        gateway_url,
        headers={"Authorization": f"Bearer {access_token}"},
    )


def get_streamable_http_mcp_client() -> MCPClient:
    """Returns an MCP Client configured for the AgentCore Gateway with OAuth auth."""
    return MCPClient(_create_gateway_transport)
