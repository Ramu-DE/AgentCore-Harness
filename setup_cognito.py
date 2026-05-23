"""
Create a Cognito User Pool for workshop gateway authentication.

Steps:
1. Create User Pool (workshop-gateway-auth)
2. Create a domain prefix for OAuth endpoints
3. Create a resource server with a custom scope for gateway invocation
4. Create an app client configured for client_credentials flow
5. Save all credentials to cognito_config.json
"""

import boto3
import json
import time
import secrets
import string

REGION = "us-west-2"
USER_POOL_NAME = "workshop-gateway-auth"
# Generate a unique domain prefix to avoid conflicts
DOMAIN_PREFIX = f"workshop-gw-{secrets.token_hex(4)}"
RESOURCE_SERVER_IDENTIFIER = "gateway"
RESOURCE_SERVER_NAME = "AgentCore Gateway"
SCOPE_NAME = "invoke"
SCOPE_DESCRIPTION = "Invoke AgentCore Gateway tools"
APP_CLIENT_NAME = "workshop-gateway-client"
CONFIG_FILE = "cognito_config.json"

cognito_client = boto3.client("cognito-idp", region_name=REGION)


def main():
    # Step 1: Create User Pool
    print("Creating User Pool...")
    create_pool_response = cognito_client.create_user_pool(
        PoolName=USER_POOL_NAME,
        Policies={
            "PasswordPolicy": {
                "MinimumLength": 8,
                "RequireUppercase": True,
                "RequireLowercase": True,
                "RequireNumbers": True,
                "RequireSymbols": False,
            }
        },
        AutoVerifiedAttributes=["email"],
        AdminCreateUserConfig={
            "AllowAdminCreateUserOnly": True,
        },
    )
    user_pool_id = create_pool_response["UserPool"]["Id"]
    print(f"  User Pool ID: {user_pool_id}")

    # Step 2: Create domain for OAuth endpoints
    print(f"Creating domain prefix: {DOMAIN_PREFIX}...")
    cognito_client.create_user_pool_domain(
        Domain=DOMAIN_PREFIX,
        UserPoolId=user_pool_id,
    )
    print(f"  Domain: {DOMAIN_PREFIX}")

    # Step 3: Create resource server with custom scope
    print("Creating resource server...")
    cognito_client.create_resource_server(
        UserPoolId=user_pool_id,
        Identifier=RESOURCE_SERVER_IDENTIFIER,
        Name=RESOURCE_SERVER_NAME,
        Scopes=[
            {
                "ScopeName": SCOPE_NAME,
                "ScopeDescription": SCOPE_DESCRIPTION,
            }
        ],
    )
    full_scope = f"{RESOURCE_SERVER_IDENTIFIER}/{SCOPE_NAME}"
    print(f"  Resource Server: {RESOURCE_SERVER_IDENTIFIER}")
    print(f"  Scope: {full_scope}")

    # Step 4: Create app client for machine-to-machine (client_credentials) flow
    print("Creating app client...")
    create_client_response = cognito_client.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName=APP_CLIENT_NAME,
        GenerateSecret=True,
        ExplicitAuthFlows=[],
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=[full_scope],
        AllowedOAuthFlowsUserPoolClient=True,
        SupportedIdentityProviders=["COGNITO"],
    )
    client_id = create_client_response["UserPoolClient"]["ClientId"]
    client_secret = create_client_response["UserPoolClient"]["ClientSecret"]
    print(f"  Client ID: {client_id}")
    print(f"  Client Secret: {client_secret[:8]}...")

    # Step 5: Build config and save
    token_endpoint = f"https://{DOMAIN_PREFIX}.auth.{REGION}.amazoncognito.com/oauth2/token"
    discovery_url = f"https://cognito-idp.{REGION}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"

    config = {
        "user_pool_id": user_pool_id,
        "domain": DOMAIN_PREFIX,
        "domain_url": f"https://{DOMAIN_PREFIX}.auth.{REGION}.amazoncognito.com",
        "client_id": client_id,
        "client_secret": client_secret,
        "token_endpoint": token_endpoint,
        "discovery_url": discovery_url,
        "scope": full_scope,
        "region": REGION,
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nConfiguration saved to {CONFIG_FILE}")
    print(f"\n--- Cognito Configuration ---")
    print(f"  User Pool ID:    {user_pool_id}")
    print(f"  Domain:          {DOMAIN_PREFIX}")
    print(f"  Client ID:       {client_id}")
    print(f"  Client Secret:   {client_secret}")
    print(f"  Token Endpoint:  {token_endpoint}")
    print(f"  Discovery URL:   {discovery_url}")
    print(f"  Scope:           {full_scope}")


if __name__ == "__main__":
    main()
