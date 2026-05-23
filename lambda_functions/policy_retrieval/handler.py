"""
Lambda function for retrieving return policies from a Bedrock Knowledge Base.
Used as an AgentCore Gateway Lambda target.

Reads the Knowledge Base ID from SSM parameter /app/workshop/kb/knowledge-base-id
and uses the Bedrock Agent Runtime retrieve API to fetch relevant policy documents.
"""

import json
import boto3

REGION = "us-west-2"
SSM_PARAM_NAME = "/app/workshop/kb/knowledge-base-id"

# Delimiter used by AgentCore Gateway to prefix tool names with target name
DELIMITER = "___"

# Initialize clients
ssm_client = boto3.client("ssm", region_name=REGION)
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)

# Cache the Knowledge Base ID (resolved once per Lambda cold start)
_knowledge_base_id: str | None = None


def get_knowledge_base_id() -> str:
    """Retrieve the Knowledge Base ID from SSM Parameter Store (cached)."""
    global _knowledge_base_id
    if _knowledge_base_id is None:
        response = ssm_client.get_parameter(Name=SSM_PARAM_NAME)
        _knowledge_base_id = response["Parameter"]["Value"]
    return _knowledge_base_id


def lambda_handler(event: dict, context) -> dict:
    """
    Entry point for the Lambda function.

    Args:
        event: A map of input properties from the tool's inputSchema.
               Expected: {"query": "...", "country": "US"} (country is optional)
        context: Contains AgentCore Gateway metadata including the tool name.

    Returns:
        A JSON-serializable dict with retrieved policy excerpts.
    """
    # Extract the tool name (strip target prefix)
    original_tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    tool_name = original_tool_name[original_tool_name.index(DELIMITER) + len(DELIMITER):]

    if tool_name == "policy_retrieval":
        return handle_policy_retrieval(event)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


def handle_policy_retrieval(event: dict) -> dict:
    """
    Retrieve return policy documents from the Bedrock Knowledge Base.

    Expected input:
        {
            "query": "What is the return policy for electronics?",
            "country": "US"  # optional filter
        }
    """
    query = event.get("query")
    if not query:
        return {"error": "query is required"}

    kb_id = get_knowledge_base_id()

    # Build the retrieve request
    retrieve_kwargs: dict = {
        "knowledgeBaseId": kb_id,
        "retrievalQuery": {"text": query},
    }

    # Apply country metadata filter if provided
    country = event.get("country")
    if country:
        retrieve_kwargs["retrievalConfiguration"] = {
            "vectorSearchConfiguration": {
                "filter": {
                    "equals": {
                        "key": "country",
                        "value": country,
                    }
                }
            }
        }

    response = bedrock_agent_runtime.retrieve(**retrieve_kwargs)

    # Format the results into clean excerpts
    results = []
    for result in response.get("retrievalResults", []):
        content = result.get("content", {}).get("text", "")
        metadata = result.get("metadata", {})
        score = result.get("score", 0.0)
        source = result.get("location", {}).get("s3Location", {}).get("uri", "unknown")

        results.append({
            "text": content,
            "source": source,
            "country": metadata.get("country", "unknown"),
            "score": round(score, 4),
        })

    return {
        "knowledge_base_id": kb_id,
        "query": query,
        "results": results,
        "result_count": len(results),
    }
