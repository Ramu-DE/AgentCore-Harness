"""
Test the AgentCore Gateway MCP endpoint.
1. Get a JWT token from Cognito using client_credentials flow
2. Call the gateway's /mcp endpoint to list available tools
"""

import json
import requests
import base64

# Load Cognito config
with open("cognito_config.json") as f:
    cognito = json.load(f)

# Gateway URL from deployed state
GATEWAY_URL = "https://agentcoreproject-workshop-gateway-9fzwzqlzaa.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp"

# Step 1: Get JWT token from Cognito
print("=== Step 1: Obtaining JWT token from Cognito ===")
token_endpoint = cognito["token_endpoint"]
client_id = cognito["client_id"]
client_secret = cognito["client_secret"]
scope = cognito["scope"]

# client_credentials grant uses Basic auth with client_id:client_secret
auth_string = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

token_response = requests.post(
    token_endpoint,
    headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_string}",
    },
    data={
        "grant_type": "client_credentials",
        "scope": scope,
    },
)

if token_response.status_code != 200:
    print(f"ERROR: Failed to get token: {token_response.status_code}")
    print(token_response.text)
    exit(1)

token_data = token_response.json()
access_token = token_data["access_token"]
print(f"Token obtained successfully (expires in {token_data.get('expires_in', '?')}s)")
print(f"Token type: {token_data.get('token_type', '?')}")

# Step 2: Call the MCP endpoint to list tools
print("\n=== Step 2: Calling MCP tools/list ===")
print(f"Gateway URL: {GATEWAY_URL}")

# MCP uses JSON-RPC format
mcp_request = {
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/list",
    "params": {},
}

mcp_response = requests.post(
    GATEWAY_URL,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    },
    json=mcp_request,
)

print(f"Response status: {mcp_response.status_code}")

if mcp_response.status_code == 200:
    result = mcp_response.json()
    print("\n=== Available Tools ===")
    tools = result.get("result", {}).get("tools", [])
    print(f"Total tools: {len(tools)}\n")
    for tool in tools:
        print(f"  Tool: {tool['name']}")
        print(f"    Description: {tool.get('description', 'N/A')}")
        input_schema = tool.get("inputSchema", {})
        props = input_schema.get("properties", {})
        if props:
            print(f"    Parameters: {', '.join(props.keys())}")
        print()
else:
    print(f"ERROR: {mcp_response.status_code}")
    print(mcp_response.text[:1000])
