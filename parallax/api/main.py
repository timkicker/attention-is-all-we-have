"""Parallax API: `uvicorn api.main:app`. Every JSON response carries `sql`, the statements behind it."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import cache, sqllog
from api.db import close_all
from api.routes import ask, atlas, check, compare, dropped, health, ingest, search, sources, timeline, topics
from contract.db import load_env

load_env()
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("parallax.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from pipeline import job

    try:
        job.ensure_tables()  # an existing seed database gains the ingest tables, nothing is dropped
    except Exception as e:
        logging.getLogger("parallax").warning("ingest tables not ensured: %s", e)
    if os.environ.get("INGEST_WORKER", "1") != "0":
        ingest.WORKER = job.Worker(after_job=cache.clear)
        ingest.WORKER.start()
    yield
    if ingest.WORKER:
        ingest.WORKER.close()
        ingest.WORKER = None
    close_all()


app = FastAPI(title="Parallax API", version="1", lifespan=lifespan)
for module in (health, topics, compare, timeline, dropped, check, sources, ask, atlas, search, ingest):
    app.include_router(module.router)


async def _with_sql(request: Request, call_next) -> tuple[Response, str | None, list[dict], bytes | None]:
    """Run the route with its statements captured; JSON bodies get them as `sql`. Returns the body when JSON."""
    with sqllog.capture() as statements:
        response = await call_next(request)
        panel = sqllog.current_panel()
    if not response.headers.get("content-type", "").startswith("application/json"):
        return response, panel, statements, None
    body = b"".join([chunk async for chunk in response.body_iterator])
    data = json.loads(body)
    if response.status_code < 400 and isinstance(data, dict):
        data.setdefault("sql", statements)
        sqllog.remember(panel, statements)
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    out = json.dumps(data, ensure_ascii=False).encode()
    return (
        Response(out, status_code=response.status_code, headers=headers, media_type="application/json"),
        panel,
        statements,
        out,
    )


@app.middleware("http")
async def attach_sql(request: Request, call_next):
    if not request.url.path.startswith("/api/") or request.url.path.startswith("/api/sql/"):
        return await call_next(request)
    key = cache.key(request)
    if key is None:
        response, *_ = await _with_sql(request, call_next)
        if request.method not in ("GET", "HEAD", "OPTIONS") and response.status_code < 400:
            cache.clear()  # a write (check, ingest) can change what the read routes return
        return response
    async with cache.single_flight(key):
        hit = cache.get(key)
        if hit is None:
            gen = cache.generation()
            response, panel, statements, body = await _with_sql(request, call_next)
            if response.status_code == 200 and body is not None:
                headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
                cache.put(key, gen, body, headers, panel, statements)
            return response
    sqllog.remember(hit.panel, hit.statements)  # "Under the hood" shows the statements behind what was served
    return Response(hit.body, status_code=200, headers=hit.headers, media_type="application/json")


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    detail = (
        exc.detail if isinstance(exc.detail, dict) else {"code": f"http_{exc.status_code}", "message": str(exc.detail)}
    )
    return JSONResponse({"error": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    """Anything unexpected: logged with its trace, answered in the error shape of the contract, details stay here."""
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"error": {"code": "internal", "message": "Something went wrong on our side."}}, 500)


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
