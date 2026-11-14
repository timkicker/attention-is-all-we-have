"""Parallax API: `uvicorn api.main:app`. Every JSON response carries `sql`, the statements behind it."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import sqllog
from api.db import close_all
from api.routes import ask, atlas, check, compare, dropped, health, sources, timeline, topics
from contract.db import load_env

load_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_all()


app = FastAPI(title="Parallax API", version="1", lifespan=lifespan)
for module in (health, topics, compare, timeline, dropped, check, sources, ask, atlas):
    app.include_router(module.router)


@app.middleware("http")
async def attach_sql(request: Request, call_next):
    if not request.url.path.startswith("/api/") or request.url.path.startswith("/api/sql/"):
        return await call_next(request)
    with sqllog.capture() as statements:
        response = await call_next(request)
        panel = sqllog.current_panel()
    if response.headers.get("content-type", "").startswith("application/json"):
        body = b"".join([chunk async for chunk in response.body_iterator])
        data = json.loads(body)
        if response.status_code < 400 and isinstance(data, dict):
            data.setdefault("sql", statements)
            if panel:
                sqllog.LAST[panel] = statements
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(
            json.dumps(data, ensure_ascii=False),
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    detail = (
        exc.detail if isinstance(exc.detail, dict) else {"code": f"http_{exc.status_code}", "message": str(exc.detail)}
    )
    return JSONResponse({"error": detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(x) for x in first.get("loc", []))
    return JSONResponse({"error": {"code": "bad_request", "message": f"{loc}: {first.get('msg', 'invalid')}"}}, 422)


DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if DIST.is_dir():
    # The built web app (make web-build) is served from the same origin, so the demo is one process.

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str):
        if path.startswith("api/"):
            return JSONResponse({"error": {"code": "not_found", "message": f"No route /{path}."}}, 404)
        file = (DIST / path).resolve()
        if path and file.is_file() and file.is_relative_to(DIST):
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
