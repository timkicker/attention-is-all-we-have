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

from . import accounts, agent_v1, connect, settings, ui
from .accounts import get_accounts
from .agent_v1 import ACCOUNT_ID
from .mcp_server import ACCOUNT
from .mcp_server import server as mcp_server
from .state import get_ctx

SPA = ROOT / "src" / "frontend" / "build"


class McpMount:
    """MCP over streamable HTTP at /mcp. Its session manager runs once per instance, so every app start
    builds a fresh one."""

    def __init__(self):
        self.app = None

    async def __call__(self, scope, receive, send):
        if self.app is None:
            raise RuntimeError("MCP is not started")
        if scope["type"] == "http":
            scope = dict(scope)
            scope.pop(ACCOUNT, None)
            path = scope["path"][len(scope.get("root_path", "")):]
            k = re.match(r"/k/([^/]*)(?=/|$)", path)
            if k:  # /mcp/k/{account}/: the same MCP server, the account on the scope for the tools to read
                account = k.group(1)
                if not ACCOUNT_ID.fullmatch(account) or get_accounts().get(account) is None:
                    await JSONResponse({"detail": f"no kitchen {account}"}, status_code=404)(scope, receive, send)
                    return
                scope["root_path"] = scope.get("root_path", "") + k.group(0)
                scope[ACCOUNT] = account
        await self.app(scope, receive, send)


mcp_app = McpMount()


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
    mcp_app.app = mcp_server.streamable_http_app(streamable_http_path="/", host="127.0.0.1",
                                                 transport_security=mcp_security(ctx.mcp_hosts))
    async with mcp_server.session_manager.run():
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
app.include_router(ui.session_router)
app.include_router(accounts.router)
app.include_router(connect.web_router())
app.mount("/mcp", mcp_app)


def _err(status: int):
    def handler(_req: Request, exc: Exception) -> JSONResponse:
        headers = {"WWW-Authenticate": "SD-JWT"} if status == 401 else None
        return JSONResponse({"detail": str(exc).strip("'")}, status_code=status, headers=headers)
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
