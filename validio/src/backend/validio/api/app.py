import json
import logging
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from mcp.server.transport_security import TransportSecuritySettings

from validio.api.steady import router as steady_router
from validio.config import ROOT
from validio.orders.service import (
    ApproveRefused,
    IdempotencyConflict,
    OrderError,
    OrderStateError,
    ServiceClosed,
)
from validio.orders.store import NotFound
from validio.orders.supply import RequestError
from validio.policy.decide import load_policy, policy_file
from validio.policy.mandate import MandateError
from validio.valio.budget import CallBudgetExceeded
from validio.valio.client import ReplayMiss, ValioUnavailable

from . import accounts, activity, agent_v1, connect, settings, ui
from .accounts import get_accounts
from .agent_v1 import ACCOUNT_ID
from .mcp_server import ACCOUNT, CONNECTOR, connector_server
from .mcp_server import server as mcp_server
from .state import get_ctx

SPA = ROOT / "src" / "frontend" / "build"


class McpMount:
    """MCP over streamable HTTP at /mcp. Its session manager runs once per instance, so every app start
    builds a fresh one."""

    def __init__(self):
        self.app = None
        self.connector = None  # /mcp/c/{token}/, its own MCP server: no spendPass, Validio signs

    async def __call__(self, scope, receive, send):
        if self.app is None:
            raise RuntimeError("MCP is not started")
        if scope["type"] == "http":
            scope = dict(scope)
            scope.pop(ACCOUNT, None)
            scope.pop(CONNECTOR, None)
            path = scope["path"][len(scope.get("root_path", "")):]
            c = re.match(r"/c/([^/]*)(?=/|$)", path)
            if c:  # /mcp/c/{token}/: only while the kitchen keeps that connection, else 404 like an unknown kitchen
                from .connect import connector_ctx

                receive, name = await client_name(scope, receive)
                if connector_ctx(c.group(1), touch=True, name=name) is None:
                    await JSONResponse({"detail": "no such connector"}, status_code=404)(scope, receive, send)
                    return
                scope["root_path"] = scope.get("root_path", "") + c.group(0)
                scope[CONNECTOR] = c.group(1)
                await self.connector(scope, receive, send)
                return
            k = re.match(r"/k/([^/]*)(?=/|$)", path)
            if k:  # /mcp/k/{account}/: the same MCP server, the account on the scope for the tools to read
                account = k.group(1)
                if not ACCOUNT_ID.fullmatch(account) or get_accounts().get(account) is None:
                    await JSONResponse({"detail": f"no kitchen {account}"}, status_code=404)(scope, receive, send)
                    return
                scope["root_path"] = scope.get("root_path", "") + k.group(0)
                scope[ACCOUNT] = account
        await self.app(scope, receive, send)


class RedactConnector(logging.Filter):
    """Access log lines never carry a connector token: /mcp/c/<token>/ is logged as /mcp/c/***/."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(CONNECTOR_PATH.sub(r"\1***", a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = CONNECTOR_PATH.sub(r"\1***", record.msg)
        return True


CONNECTOR_PATH = re.compile(r"(/mcp/c/)[^/\s?\"]+")
for _name in ("uvicorn.access", "uvicorn.error", "httpx"):
    logging.getLogger(_name).addFilter(RedactConnector())

mcp_app = McpMount()
MAX_PEEK = 1 << 20  # a body larger than this is passed on unread for the name
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"  # the 2026 protocol stamps clientInfo on every request


def info_name(msg) -> str | None:
    """The client's display title, else its name, from an initialize's clientInfo or a later protocol's
    `_meta` stamp (server/discover and every request after it)."""
    params = msg.get("params") if isinstance(msg, dict) else None
    if not isinstance(params, dict):
        return None
    meta = params.get("_meta")
    info = params.get("clientInfo") if msg.get("method") == "initialize" else None
    if info is None and isinstance(meta, dict):
        info = meta.get(CLIENT_INFO_META)
    if not isinstance(info, dict):
        return None
    title = info.get("title")
    return title if isinstance(title, str) and title.strip() else info.get("name")


async def client_name(scope, receive):
    """The name the MCP client gives in this request (`info_name`), and a receive that hands the MCP server the
    same body again. A GET, a body that is no JSON or one without client info gives None."""
    if scope.get("method") != "POST":
        return receive, None
    chunks, size, more = [], 0, True
    first = None
    while more:
        msg = await receive()
        if msg["type"] != "http.request":  # the client went away: hand that on as it came
            first = msg
            break
        chunks.append(msg.get("body", b""))
        size += len(chunks[-1])
        more = msg.get("more_body", False)
        if size > MAX_PEEK:
            break
    body = b"".join(chunks)
    sent = False

    async def replay():
        nonlocal sent
        if not sent:
            sent = True
            if first is not None and not body:
                return first
            return {"type": "http.request", "body": body, "more_body": more}
        return await receive()

    if more:
        return replay, None
    try:
        msg = json.loads(body)
    except ValueError:
        return replay, None
    return replay, info_name(msg[0] if isinstance(msg, list) and msg else msg)


LOCAL_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
LOCAL_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


def mcp_security(hosts: list[str]) -> TransportSecuritySettings:
    """DNS rebinding protection stays on; VALIDIO_MCP_HOSTS adds the public hostname (Modal)."""
    return TransportSecuritySettings(
        allowed_hosts=LOCAL_HOSTS + [x for h in hosts for x in (h, f"{h}:*")],
        allowed_origins=LOCAL_ORIGINS + [f"https://{h}" for h in hosts])


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_policy(policy_file())  # a broken policy file stops the app, never a silent rule change
    ctx = get_ctx()
    if missing := ctx.startup_problems():
        raise RuntimeError(f"VALIDIO_PUBLIC=1 needs {', '.join(missing)}; refusing to start open")
    security = mcp_security(ctx.mcp_hosts)
    mcp_app.app = mcp_server.streamable_http_app(streamable_http_path="/", host="127.0.0.1",
                                                 transport_security=security)
    mcp_app.connector = connector_server.streamable_http_app(streamable_http_path="/", host="127.0.0.1",
                                                             transport_security=security)
    async with mcp_server.session_manager.run(), connector_server.session_manager.run():
        yield


app = FastAPI(title="Validio", version="0.1.0", lifespan=lifespan,
              description="Agent API under /agent/v1 (writes need `Authorization: SD-JWT <presentation>`), "
                          "web app API under /api, MCP at /mcp.")
app.include_router(steady_router, dependencies=[Depends(ui.kitchen)])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(agent_v1.router)
app.include_router(agent_v1.account_router)
app.include_router(ui.router)
app.include_router(settings.router)
app.include_router(activity.router)
app.include_router(ui.session_router)
app.include_router(accounts.router)
app.include_router(connect.web_router())
app.mount("/mcp", mcp_app)


CODES = ((ApproveRefused, "refused"), (IdempotencyConflict, "conflict"), (OrderStateError, "already"),
         (ValioUnavailable, "valio_down"))


def _err(status: int):
    def handler(_req: Request, exc: Exception) -> JSONResponse:
        """{"detail": the sentence, as before} plus "code" where a screen must tell cases apart: a 409 is
        "refused" (Valio was asked again and the order was not placed, "refusedText" says why for the owner),
        "already" (the order was decided before) or "conflict" (an idempotency key used for another body)."""
        headers = {"WWW-Authenticate": "SD-JWT"} if status == 401 else None
        body: dict = {"detail": str(exc).strip("'")}
        if code := next((c for t, c in CODES if isinstance(exc, t)), None):
            body["code"] = code
        if isinstance(exc, ApproveRefused):
            body["refusedText"] = exc.refused_text
        return JSONResponse(body, status_code=status, headers=headers)
    return handler


for exc, status in ((MandateError, 401), (NotFound, 404), (OrderStateError, 409), (IdempotencyConflict, 409),
                    (ApproveRefused, 409), (RequestError, 422), (OrderError, 422), (CallBudgetExceeded, 422),
                    (ServiceClosed, 503), (ValioUnavailable, 503), (ReplayMiss, 503)):
    app.add_exception_handler(exc, _err(status))


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    """The built web app, with index.html for every route the SPA knows."""
    if path.startswith(("api/", "agent/", "mcp")):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    f = (SPA / path).resolve()
    if path and f.is_file() and f.is_relative_to(SPA.resolve()):
        return FileResponse(f)
    index = SPA / "index.html"
    if index.is_file():
        return FileResponse(index)
    return JSONResponse({"detail": "web app not built, run make demo"}, status_code=404)
