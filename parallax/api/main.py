"""Parallax API: `uvicorn api.main:app`. Every JSON response carries `sql`, the statements behind it."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import cache, sqllog, warm
from api.db import close_all
from api.routes import ask, atlas, check, compare, dropped, health, ingest, search, sources, timeline, topics
from contract.db import load_env

load_env()
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("parallax.api")


_LOOP = None  # the server's event loop, for warming the cache again after an ingest (worker thread)
# A Differences page of a date the cache does not hold is seconds of exact vector search. A room picking dates at once
# held every thread of the pool and every CPU of the database, and even the page shell waited 20 s. At most HEAVY_MAX
# run at a time; the others wait here without a thread, in order.
_HEAVY = asyncio.Semaphore(int(os.environ.get("HEAVY_MAX", "3")))
# Under the hood runs its vector query live (about a second). Behind the cold pages it waited 95 s, so it has its own.
_HOOD = asyncio.Semaphore(2)


def _heavy(request: Request) -> bool:
    return request.url.path == "/api/compare" and "h" not in request.query_params


def data_changed(topic: str | None = None) -> None:
    """An ingest stored another edition of topic or finished: drop the cached answers computed from the old data."""
    cache.clear(topic)
    dropped.clear_cache(topic)


def job_done(topic: str | None = None) -> None:
    data_changed(topic)
    if _LOOP is not None:
        warm.start(app, _LOOP)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from pipeline import job

    try:
        job.ensure_tables()  # an existing seed database gains the ingest tables, nothing is dropped
    except Exception as e:
        logging.getLogger("parallax").warning("ingest tables not ensured: %s", e)
    if os.environ.get("INGEST_WORKER", "1") != "0":
        ingest.WORKER = job.Worker(after_job=job_done)
        ingest.WORKER.start()
    global _LOOP
    _LOOP = asyncio.get_running_loop()
    warm.start(app)
    yield
    _LOOP = None
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
        if request.url.path == "/api/sql/vector":
            async with _HOOD:
                return await call_next(request)
        return await call_next(request)
    key = cache.key(request)
    if key is None:
        response, *_ = await _with_sql(request, call_next)
        if request.method not in ("GET", "HEAD", "OPTIONS") and response.status_code < 400 and _changes_data(request):
            cache.clear()  # an ingest can change what the read routes return
        return response
    async with cache.single_flight(key):
        hit = cache.get(key)
        if hit is None:
            gen = cache.generation()
            if _heavy(request):
                async with _HEAVY:
                    response, panel, statements, body = await _with_sql(request, call_next)
            else:
                response, panel, statements, body = await _with_sql(request, call_next)
            if response.status_code != 200 or body is None:
                return response
            headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
            return _cached_response(request, cache.put(key, gen, body, headers, panel, statements))
    sqllog.remember(hit.panel, hit.statements)  # "Under the hood" shows the statements behind what was served
    return _cached_response(request, hit)


def _changes_data(request: Request) -> bool:
    """POST /api/check only adds its own run (check_run, check_claim), which no cached GET answer reads: a check
    must not throw away the warm Differences pages of every other visitor."""
    return request.url.path not in ("/api/check", "/api/ingest")  # POST /api/ingest clears its own topic


def _cached_response(request: Request, entry: cache.Entry) -> Response:
    """A cached answer: 304 when the browser holds this version, else gzip when accepted (compressed once)."""
    headers = dict(entry.headers)
    headers["ETag"] = entry.etag
    headers["Cache-Control"] = "no-cache"  # the browser may keep it but asks each time; the answer is then a 304
    headers["Vary"] = "Accept-Encoding"
    if entry.etag in request.headers.get("if-none-match", ""):
        return Response(status_code=304, headers=headers)
    if "gzip" in request.headers.get("accept-encoding", ""):
        headers["Content-Encoding"] = "gzip"
        return Response(entry.gz, status_code=200, headers=headers, media_type="application/json")
    return Response(entry.body, status_code=200, headers=headers, media_type="application/json")


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

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)  # HEAD: link previews, checks
    async def web(path: str):  # async: the page shell must not wait for a thread behind slow API requests
        if path.startswith("api/"):
            return JSONResponse({"error": {"code": "not_found", "message": f"No route /{path}."}}, 404)
        file = (DIST / path).resolve()
        if path and file.is_file() and file.is_relative_to(DIST):
            if path.startswith("assets/"):  # vite puts a content hash in every name under assets/
                return FileResponse(file, headers={"Cache-Control": "public, max-age=31536000, immutable"})
            return FileResponse(file)
        # the page names the hashed assets of the current build, so it is asked for again after every deploy
        index = (DIST / "index.html").read_bytes()  # small and in the page cache; FileResponse reads in a thread
        return Response(index, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})
