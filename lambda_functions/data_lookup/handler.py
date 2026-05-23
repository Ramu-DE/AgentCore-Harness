"""
Lambda function for DynamoDB data lookups (orders, customers, products).
Used as an AgentCore Gateway Lambda target.

Supports five tools:
  - order_lookup: Query orders by customer_id
  - user_lookup: Get customer details by customer_id
  - product_lookup: Get product details by product_id
  - find_returned_products: Find all orders with RETURNED status, enriched with product names
  - process_refund: Verify an order and return refund confirmation with product details
"""

import json
import boto3
from boto3.dynamodb.conditions import Key

# Initialize DynamoDB resource in us-west-2
dynamodb = boto3.resource("dynamodb", region_name="us-west-2")

# Table references
orders_table = dynamodb.Table("workshop-orders")
customers_table = dynamodb.Table("workshop-customers")
products_table = dynamodb.Table("workshop-products")

# Delimiter used by AgentCore Gateway to prefix tool names with target name
DELIMITER = "___"


def lambda_handler(event: dict, context) -> dict:
    """
    Entry point for the Lambda function.

    Args:
        event: A map of input properties from the tool's inputSchema.
        context: Contains AgentCore Gateway metadata including the tool name
                 in context.client_context.custom['bedrockAgentCoreToolName'].

    Returns:
        A JSON-serializable dict with the tool's response.
    """
    # Extract the tool name, stripping the target prefix
    original_tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    tool_name = original_tool_name[original_tool_name.index(DELIMITER) + len(DELIMITER):]

    # Route to the appropriate handler based on tool name
    if tool_name == "order_lookup":
        return handle_order_lookup(event)
    elif tool_name == "user_lookup":
        return handle_user_lookup(event)
    elif tool_name == "product_lookup":
        return handle_product_lookup(event)
    elif tool_name == "find_returned_products":
        return handle_find_returned_products(event)
    elif tool_name == "process_refund":
        return handle_process_refund(event)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


def handle_order_lookup(event: dict) -> dict:
    """
    Query all orders for a given customer.

    Expected input: {"customer_id": "C-01"}
    """
    customer_id = event.get("customer_id")
    if not customer_id:
        return {"error": "customer_id is required"}

    response = orders_table.query(
        KeyConditionExpression=Key("customer_id").eq(customer_id)
    )

    orders = []
    for item in response.get("Items", []):
        orders.append({
            "customer_id": item.get("customer_id"),
            "product_id": item.get("product_id"),
            "purchased_date": item.get("purchased_date"),
            "status": item.get("status"),
        })

    return {"orders": orders, "count": len(orders)}


def handle_user_lookup(event: dict) -> dict:
    """
    Get customer details by customer_id.

    Expected input: {"customer_id": "C-01"}
    """
    customer_id = event.get("customer_id")
    if not customer_id:
        return {"error": "customer_id is required"}

    response = customers_table.get_item(Key={"customer_id": customer_id})
    item = response.get("Item")

    if not item:
        return {"error": f"Customer {customer_id} not found"}

    return {
        "customer_id": item.get("customer_id"),
        "name": item.get("name"),
        "country_code": item.get("country_code"),
    }


def handle_product_lookup(event: dict) -> dict:
    """
    Get product details by product_id.

    Expected input: {"product_id": "P-001"}
    """
    product_id = event.get("product_id")
    if not product_id:
        return {"error": "product_id is required"}

    response = products_table.get_item(Key={"product_id": product_id})
    item = response.get("Item")

    if not item:
        return {"error": f"Product {product_id} not found"}

    return {
        "product_id": item.get("product_id"),
        "product_name": item.get("product_name"),
        "product_category": item.get("product_category"),
        "provider": item.get("provider"),
    }


def handle_find_returned_products(event: dict) -> dict:
    """
    Find all orders with status RETURNED across all customers, enriched with product names.

    Uses a DynamoDB Scan with a filter on status since we need to query across
    all partition keys (customer_ids). Enriches each result with the product name
    from the workshop-products table.

    Expected input: {} (no parameters required)
    """
    # Scan the orders table for all items with status "RETURNED"
    returned_orders = []
    scan_kwargs = {
        "FilterExpression": "status = :status",
        "ExpressionAttributeValues": {":status": "RETURNED"},
    }

    # Handle pagination in case there are many returned orders
    while True:
        response = orders_table.scan(**scan_kwargs)
        returned_orders.extend(response.get("Items", []))
        # Continue scanning if there are more pages
        if "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        else:
            break

    # Enrich each order with the product name from the products table
    results = []
    for order in returned_orders:
        product_id = order.get("product_id")
        product_name = None

        if product_id:
            product_response = products_table.get_item(Key={"product_id": product_id})
            product_item = product_response.get("Item")
            if product_item:
                product_name = product_item.get("product_name")

        results.append({
            "customer_id": order.get("customer_id"),
            "product_id": product_id,
            "product_name": product_name,
            "purchased_date": order.get("purchased_date"),
            "status": order.get("status"),
        })

    return {"returned_products": results, "count": len(results)}


def handle_process_refund(event: dict) -> dict:
    """
    Process a refund for a specific order.

    Verifies the order exists using customer_id and product_id (composite key),
    then returns a refund confirmation with product details.
    Note: In this workshop environment, the DynamoDB table is read-only,
    so we simulate the status update in the response.

    Expected input: {"customer_id": "C-01", "product_id": "P-001"}
    """
    customer_id = event.get("customer_id")
    product_id = event.get("product_id")

    if not customer_id:
        return {"error": "customer_id is required"}
    if not product_id:
        return {"error": "product_id is required"}

    # Verify the order exists
    order_response = orders_table.get_item(
        Key={"customer_id": customer_id, "product_id": product_id}
    )
    order = order_response.get("Item")

    if not order:
        return {"error": f"Order not found for customer {customer_id}, product {product_id}"}

    # Look up product details for the confirmation
    product_response = products_table.get_item(Key={"product_id": product_id})
    product = product_response.get("Item", {})

    return {
        "refund_status": "PROCESSED",
        "customer_id": customer_id,
        "product_id": product_id,
        "product_name": product.get("product_name"),
        "product_category": product.get("product_category"),
        "previous_status": order.get("status"),
        "new_status": "REFUNDED",
        "purchased_date": order.get("purchased_date"),
    }
