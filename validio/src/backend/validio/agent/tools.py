"""The MCP tools as the kitchen's agent sees them, from the blueprint's tool table.

The model never writes idempotency keys or the Spend Pass: the port adds both. Supplier free text
never reaches the model: `redact` drops every field that carries it before a result goes back."""

import re
from typing import Any

_LINE = {
    "type": "object",
    "description": "One request line: either free text, or a product id with an amount in its sales unit.",
    "properties": {
        "text": {"type": "string"},
        "productId": {"type": "string"},
        "quantity": {"type": "number"},
        "unit": {"type": "string"},
    },
}
_CHOICE = {
    "type": "object",
    "properties": {
        "productId": {"type": "string"},
        "salesQty": {"type": "integer"},
        "isSubstitute": {"type": "boolean"},
        "onValioList": {"type": "boolean"},
    },
    "required": ["productId", "salesQty"],
}

TOOLS: list[dict[str, Any]] = [
    {"name": "search_products",
     "description": "Search Valio's catalog. Static data only, no live call.",
     "parameters": {"type": "object", "properties": {
         "text": {"type": "string"}, "category": {"type": "string"},
         "claims": {"type": "array", "items": {"type": "string"}},
         "limit": {"type": "integer", "description": "at most 20"}}, "required": ["text"]}},
    {"name": "request_supply",
     "description": "Ask Validio for supplies. Returns status, ranked options per line, the decision, "
                    "substitutes, the split and how many products were checked live.",
     "parameters": {"type": "object", "properties": {
         "lines": {"type": "array", "items": _LINE},
         "deliverBy": {"type": "string", "description": "ISO date"}}, "required": ["lines", "deliverBy"]}},
    {"name": "get_request",
     "description": "Read a request result again.",
     "parameters": {"type": "object", "properties": {"requestId": {"type": "string"}},
                    "required": ["requestId"]}},
    {"name": "confirm_order",
     "description": "Confirm the chosen products and amounts of a request. Validio prices everything again.",
     "parameters": {"type": "object", "properties": {
         "requestId": {"type": "string"}, "choice": {"type": "array", "items": _CHOICE}},
         "required": ["requestId", "choice"]}},
    {"name": "get_order",
     "description": "Read an order and its state.",
     "parameters": {"type": "object", "properties": {"orderId": {"type": "string"}}, "required": ["orderId"]}},
    {"name": "renew_steady_order",
     "description": "Renew this week's Steady Order. Lines that match the usual pattern are ordered automatically, "
                    "the rest wait for the owner with the reason.",
     "parameters": {"type": "object", "properties": {"orderId": {"type": "string", "description": "e.g. S-1"}},
                    "required": ["orderId"]}},
]
WRITE_TOOLS = {"request_supply", "confirm_order"}  # get an idempotency key from the port
PASS_TOOLS = WRITE_TOOLS | {"renew_steady_order", "get_request", "get_order"}  # get the Spend Pass from the port

SUPPLIER_TEXT = re.compile(r"untrusted|description|marketing|ingredient|planted|supplier", re.IGNORECASE)


def untrusted_record(obj: Any) -> bool:
    """A Fact Grade record of supplier text: {"field": "description", "value": ..., "grade": "untrusted"}."""
    return isinstance(obj, dict) and ("untrusted" in (obj.get("grade"), obj.get("level"))
                                      or SUPPLIER_TEXT.search(str(obj.get("field") or "")) is not None)


def redact(obj: Any) -> Any:
    """Drop every field whose name says it holds supplier text and every record graded untrusted,
    at any depth."""
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items() if not SUPPLIER_TEXT.search(k) and not untrusted_record(v)}
    if isinstance(obj, list):
        return [redact(v) for v in obj if not untrusted_record(v)]
    return obj
