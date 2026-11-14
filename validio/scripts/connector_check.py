"""Order the way an MCP agent that cannot sign does (a chat app connector, a coding tool): the python `mcp`
Client over streamable HTTP on a connector URL, with no spendPass and no idempotencyKey.

    uv run python scripts/connector_check.py https://<host>/mcp/c/<token>/

Prints every call and answer in short and exits 0 when the order went through Validio (ordered alone, or
waiting for the kitchen's approval). On a new connection the first call answers that Validio waits for Allow:
it prints the verification code from that answer, which must match the code on the Agent page; press Allow
there and run it again."""

import asyncio
import json
import re
import sys

from mcp import Client

LINES = [{"text": "1000 litres of lactose-free milk"}]
DELIVER_BY = "2026-11-16"  # the demo's Monday
VERIFY = re.compile(r"verification code: ([A-Z2-9]{3}-[A-Z2-9]{3})")


def _data(r) -> dict:
    if r.is_error:
        return {"error": " ".join(getattr(c, "text", "") for c in r.content)}
    data = r.structured_content
    if data is None:
        data = json.loads("".join(getattr(c, "text", "") for c in r.content) or "{}")
    return data.get("result", data) if set(data) == {"result"} else data


async def order_milk(url: str, say=print) -> dict:
    async with Client(url) as c:
        tools = (await c.list_tools()).tools
        names = sorted(t.name for t in tools)
        say(f"tools: {', '.join(names)}")
        assert all("spendPass" not in (t.input_schema or {}).get("properties", {}) for t in tools), "spendPass asked"
        req = _data(await c.call_tool("request_supply", {"lines": LINES, "deliverBy": DELIVER_BY}))
        if "error" in req:
            say(f"request_supply: {req['error']}")
            code = VERIFY.search(req["error"])
            if code:
                say(f"verification code: {code.group(1)} (must match the code on the Validio Agent page)")
            return {"request": req, "verifyCode": code.group(1) if code else None}
        outcome = (req.get("decision") or {}).get("outcome")
        say(f"request_supply: {req['id']} {outcome}: {(req.get('decision') or {}).get('sentence', '')}")
        out = {"request": req, "outcome": outcome}
        if outcome == "auto_order":
            choice = [{"productId": ln["chosen"]["productId"], "salesQty": ln["chosen"]["salesQty"]}
                      for ln in req["lines"] if ln.get("chosen")]
            order = _data(await c.call_tool("confirm_order", {"requestId": req["id"], "choice": choice}))
            say(f"confirm_order: {order.get('id')} {order.get('state') or order.get('error')}")
            out["order"] = order
        elif req.get("orderId"):
            order = _data(await c.call_tool("get_order", {"orderId": req["orderId"]}))
            say(f"get_order: {order.get('id')} {order.get('state') or order.get('error')}")
            out["order"] = order
        again = _data(await c.call_tool("get_request", {"requestId": req["id"]}))
        say(f"get_request: {again.get('id')} {again.get('status') or again.get('error')}")
        out["status"] = again.get("status")
        return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out = asyncio.run(order_milk(sys.argv[1]))
    return 0 if out.get("status") in ("ordered_alone", "waiting") else 1


if __name__ == "__main__":
    sys.exit(main())
