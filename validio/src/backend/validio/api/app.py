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

from . import agent_v1, ui
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
app.include_router(ui.router)
app.include_router(ui.session_router)
app.mount("/mcp", mcp_app)


def _err(status: int):
    def handler(_req: Request, exc: Exception) -> JSONResponse:
        headers = {"WWW-Authenticate": "SD-JWT"} if status == 401 else None
        return JSONResponse({"detail": str(exc).strip("'")}, status_code=status, headers=headers)
    return handler


for exc, status in ((MandateError, 401), (NotFound, 404), (OrderStateError, 409), (IdempotencyConflict, 409),
                    (ApproveRefused, 409), (RequestError, 422), (OrderError, 422), (CallBudgetExceeded, 422),
                    (ServiceClosed, 503)):
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
