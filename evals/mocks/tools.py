"""
In-memory mock implementations of all 6 agent tools.

Each tool:
  - Serves fixture data loaded from evals/fixtures/
  - Records every call to the active TraceRecorder
  - Returns the same dict shape as the real Lambda handlers

Usage in tests:
    recorder = TraceRecorder()
    set_recorder(recorder)
    # run agent...
    assert recorder.called_before("order_lookup", "process_refund")
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from strands import tool
except ImportError:
    # Allow importing this module without strands installed (trajectory-only tests)
    def tool(fn):  # type: ignore[misc]
        return fn

# ─── Trace recording ─────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    name: str
    args: dict
    result: dict
    timestamp: float = field(default_factory=time.time)


class TraceRecorder:
    """Records every tool call made during one agent run."""

    def __init__(self) -> None:
        self.calls: list[ToolCall] = []

    def record(self, name: str, args: dict, result: dict) -> None:
        self.calls.append(ToolCall(name=name, args=args, result=result))

    def names(self) -> list[str]:
        return [c.name for c in self.calls]

    def was_called(self, name: str) -> bool:
        return name in self.names()

    def first_index(self, name: str) -> int:
        for i, c in enumerate(self.calls):
            if c.name == name:
                return i
        return -1

    def called_before(self, first: str, second: str) -> bool:
        """Return True if `first` was called at least once before `second`."""
        i = self.first_index(first)
        j = self.first_index(second)
        return i != -1 and j != -1 and i < j

    def args_for(self, name: str) -> dict:
        """Return the args of the first call to `name`, or {}."""
        for c in self.calls:
            if c.name == name:
                return c.args
        return {}

    def result_for(self, name: str) -> dict:
        for c in self.calls:
            if c.name == name:
                return c.result
        return {}

    def reset(self) -> None:
        self.calls.clear()

    def replay(self, recorded_trajectory: list[dict]) -> None:
        """Populate the recorder from a list of {"tool": name, "args": {}} dicts."""
        for step in recorded_trajectory:
            name = step["tool"]
            args = step.get("args", {})
            # Run through the actual mock so results are realistic
            fn = _TOOL_FNS.get(name)
            if fn:
                result = fn(**args)
            else:
                result = {}
            self.record(name, args, result)


# Module-level active recorder — swapped per test via set_recorder()
_active_recorder: Optional[TraceRecorder] = None


def set_recorder(recorder: Optional[TraceRecorder]) -> None:
    global _active_recorder
    _active_recorder = recorder


def _rec(name: str, args: dict, result: dict) -> None:
    if _active_recorder is not None:
        _active_recorder.record(name, args, result)


# ─── Fixture data ─────────────────────────────────────────────────────────────

_FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> list[dict]:
    return json.loads((_FIXTURES / f"{name}.json").read_text())


_customers: dict[str, dict] = {c["customer_id"]: c for c in _load("customers")}
_products: dict[str, dict]  = {p["product_id"]: p  for p in _load("products")}
_policies: list[dict]       = _load("policies")

# Orders keyed by (customer_id, product_id)
_orders: dict[tuple[str, str], dict] = {
    (o["customer_id"], o["product_id"]): o for o in _load("orders")
}


# ─── Mock tool functions ───────────────────────────────────────────────────────

@tool
def order_lookup(customer_id: str) -> dict:
    """Look up all orders for a given customer. Returns order details including product IDs, purchase dates, and order status."""
    if customer_id not in _customers:
        result: dict = {"error": f"Customer {customer_id} not found"}
    else:
        orders = [
            {
                "customer_id": o["customer_id"],
                "product_id": o["product_id"],
                "purchased_date": o["purchased_date"],
                "status": o["status"],
            }
            for (cid, _pid), o in _orders.items()
            if cid == customer_id
        ]
        result = {"orders": orders, "count": len(orders)}
    _rec("order_lookup", {"customer_id": customer_id}, result)
    return result


@tool
def user_lookup(customer_id: str) -> dict:
    """Look up customer details by customer ID. Returns the customer name and country code."""
    customer = _customers.get(customer_id)
    if not customer:
        result = {"error": f"Customer {customer_id} not found"}
    else:
        result = {
            "customer_id": customer["customer_id"],
            "name": customer["name"],
            "country_code": customer["country_code"],
        }
    _rec("user_lookup", {"customer_id": customer_id}, result)
    return result


@tool
def product_lookup(product_id: str) -> dict:
    """Look up product details by product ID. Returns the product name, category, and provider."""
    product = _products.get(product_id)
    if not product:
        result = {"error": f"Product {product_id} not found"}
    else:
        result = {k: product[k] for k in ("product_id", "product_name", "product_category", "provider")}
    _rec("product_lookup", {"product_id": product_id}, result)
    return result


@tool
def find_returned_products() -> dict:
    """Find all orders with RETURNED status across all customers. Returns order details enriched with product names."""
    items = []
    for (cid, pid), o in _orders.items():
        if o["status"] == "RETURNED":
            product = _products.get(pid, {})
            items.append({
                "customer_id": cid,
                "product_id": pid,
                "product_name": product.get("product_name"),
                "purchased_date": o["purchased_date"],
                "status": o["status"],
            })
    result = {"returned_products": items, "count": len(items)}
    _rec("find_returned_products", {}, result)
    return result


@tool
def process_refund(customer_id: str, product_id: str) -> dict:
    """Process a refund for a specific order. Verifies the order exists and returns refund confirmation with product details."""
    order = _orders.get((customer_id, product_id))
    if not order:
        result = {"error": f"Order not found for customer {customer_id}, product {product_id}"}
    else:
        product = _products.get(product_id, {})
        result = {
            "refund_status": "PROCESSED",
            "customer_id": customer_id,
            "product_id": product_id,
            "product_name": product.get("product_name"),
            "product_category": product.get("product_category"),
            "previous_status": order["status"],
            "new_status": "REFUNDED",
            "purchased_date": order["purchased_date"],
        }
    _rec("process_refund", {"customer_id": customer_id, "product_id": product_id}, result)
    return result


@tool
def policy_retrieval(query: str, country: Optional[str] = None) -> dict:
    """Retrieve return and refund policy information from the knowledge base. Supports optional country code filtering (e.g. US, GB, MX)."""
    results = []
    query_lower = query.lower()
    for p in _policies:
        # Skip if country filter set and policy doesn't match
        if country and p["country"] not in (country, "ALL"):
            continue
        if any(kw in query_lower for kw in p.get("keywords", [])):
            results.append({
                "text": p["text"],
                "source": p["source"],
                "country": p["country"],
                "score": p["score"],
            })
    # Fallback: return top matches for the country regardless of keyword
    if not results:
        for p in _policies:
            if country in (None, p["country"], "ALL"):
                results.append({
                    "text": p["text"],
                    "source": p["source"],
                    "country": p["country"],
                    "score": p["score"],
                })
                if len(results) >= 2:
                    break
    result = {
        "knowledge_base_id": "mock-kb-001",
        "query": query,
        "results": results,
        "result_count": len(results),
    }
    _rec("policy_retrieval", {"query": query, "country": country}, result)
    return result


# Raw callables for use in TraceRecorder.replay() without @tool decoration
_TOOL_FNS: dict[str, object] = {
    "order_lookup": order_lookup,
    "user_lookup": user_lookup,
    "product_lookup": product_lookup,
    "find_returned_products": find_returned_products,
    "process_refund": process_refund,
    "policy_retrieval": policy_retrieval,
}

ALL_MOCK_TOOLS = list(_TOOL_FNS.values())
