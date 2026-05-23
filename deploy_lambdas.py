"""
Deploy both Lambda functions (data_lookup and policy_retrieval) to AWS.

Steps:
1. Read the execution role ARN from SSM parameter.
2. Zip each function's handler.py into a deployment package.
3. Create (or update) the Lambda functions in us-west-2.
4. Print the resulting Lambda ARNs.
"""

import boto3
import zipfile
import io
import os

REGION = "us-west-2"
SSM_ROLE_PARAM = "/app/workshop/lambda/execution-role-arn"

# Lambda function definitions
FUNCTIONS = [
    {
        "name": "workshop-data-lookup",
        "handler": "handler.lambda_handler",
        "code_dir": os.path.join("lambda_functions", "data_lookup"),
        "description": "Handles order, customer, and product lookups from DynamoDB for AgentCore Gateway.",
    },
    {
        "name": "workshop-policy-retrieval",
        "handler": "handler.lambda_handler",
        "code_dir": os.path.join("lambda_functions", "policy_retrieval"),
        "description": "Retrieves return policies from Bedrock Knowledge Base for AgentCore Gateway.",
    },
]


def get_role_arn(ssm_client) -> str:
    """Retrieve the Lambda execution role ARN from SSM."""
    response = ssm_client.get_parameter(Name=SSM_ROLE_PARAM)
    return response["Parameter"]["Value"]


def create_zip_package(code_dir: str) -> bytes:
    """Create an in-memory zip of the handler.py file."""
    zip_buffer = io.BytesIO()
    handler_path = os.path.join(code_dir, "handler.py")
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add handler.py at the root of the zip
        zf.write(handler_path, "handler.py")
    zip_buffer.seek(0)
    return zip_buffer.read()


def deploy_function(lambda_client, func_config: dict, role_arn: str, zip_bytes: bytes) -> str:
    """Create or update a Lambda function. Returns the function ARN."""
    func_name = func_config["name"]

    try:
        # Try to create the function
        response = lambda_client.create_function(
            FunctionName=func_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler=func_config["handler"],
            Code={"ZipFile": zip_bytes},
            Description=func_config["description"],
            Timeout=30,
            MemorySize=256,
            Publish=True,
        )
        print(f"  Created: {func_name}")
        return response["FunctionArn"]
    except lambda_client.exceptions.ResourceConflictException:
        # Function already exists — update its code and configuration
        lambda_client.update_function_configuration(
            FunctionName=func_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler=func_config["handler"],
            Description=func_config["description"],
            Timeout=30,
            MemorySize=256,
        )
        # Wait for the config update to complete before updating code
        waiter = lambda_client.get_waiter("function_updated_v2")
        waiter.wait(FunctionName=func_name)

        response = lambda_client.update_function_code(
            FunctionName=func_name,
            ZipFile=zip_bytes,
            Publish=True,
        )
        print(f"  Updated: {func_name}")
        return response["FunctionArn"]


def main():
    ssm_client = boto3.client("ssm", region_name=REGION)
    lambda_client = boto3.client("lambda", region_name=REGION)

    # Step 1: Get the execution role ARN
    role_arn = get_role_arn(ssm_client)
    print(f"Execution Role ARN: {role_arn}\n")

    # Step 2 & 3: Zip and deploy each function
    print("Deploying Lambda functions...")
    arns = []
    for func_config in FUNCTIONS:
        zip_bytes = create_zip_package(func_config["code_dir"])
        arn = deploy_function(lambda_client, func_config, role_arn, zip_bytes)
        arns.append((func_config["name"], arn))

    # Step 4: Print the ARNs
    print("\n--- Deployed Lambda ARNs ---")
    for name, arn in arns:
        print(f"  {name}: {arn}")


if __name__ == "__main__":
    main()
