"""The agent's side of the MCP connection. Adds the Spend Pass and stable idempotency keys to writes."""

import hashlib
import json
from collections.abc import Callable
from typing import Any, Self

from mcp import Client

from .tools import PASS_TOOLS, WRITE_TOOLS


def idempotency_key(name: str, args: dict[str, Any], salt: str = "") -> str:
    """Same tool and arguments give the same key, so a retried run never orders twice. A salt makes one
    run's keys its own: the demo's ask button means a new request each time it is pressed."""
    return hashlib.sha256(f"{salt}{name}|{json.dumps(args, sort_keys=True)}".encode()).hexdigest()[:24]


class McpPort:
    def __init__(self, server: Any, spend_pass: Callable[[], str] | None = None, salt: str = ""):
        self._client = Client(server)
        self._spend_pass = spend_pass
        self._salt = salt

    async def __aenter__(self) -> Self:
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.__aexit__(*exc)

    async def tool_names(self) -> list[str]:
        return [t.name for t in (await self._client.list_tools()).tools]

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        sent = dict(args)
        if name in WRITE_TOOLS:
            sent["idempotencyKey"] = idempotency_key(name, args, self._salt)
        if name in PASS_TOOLS and self._spend_pass:
            sent["spendPass"] = self._spend_pass()
        r = await self._client.call_tool(name, sent)
        if r.is_error:
            text = " ".join(getattr(c, "text", "") for c in r.content)
            return {"error": text or "tool error"}
        data = r.structured_content
        if data is None:
            text = "".join(getattr(c, "text", "") for c in r.content)
            data = json.loads(text) if text else {}
        if set(data) == {"result"}:  # MCPServer wraps non-dict returns
            data = data["result"]
        return data
