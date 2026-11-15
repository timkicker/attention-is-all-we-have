"""Fill the response cache with the pages every visitor opens first, one request at a time, through the app itself.

A Differences page for today has no cached alignment, so each of its pages is seconds of exact vector search; warm,
the first visitors after a deploy or an ingest get it from memory. WARM_CACHE=1 turns it on (deploy/
docker-compose.prod.yml); tests and local runs leave it off.
"""

import asyncio
import logging
import os

import httpx

log = logging.getLogger("parallax.warm")
PAGE = 200  # FETCH of web/src/lib/adapt/topic.ts and API_LIMIT of removed.ts: the cache key is the exact query
# The quick picks of the date button (web/src/lib/ui/AsOf.svelte). Most have no align rows, so a cold one is seconds
# of exact search per page; warmed last, after the pages of today.
PICK_DATES = ("2020-01-01", "2015-01-01", "2010-01-01", "2008-01-01")


_state = {"running": False, "again": False}  # touched on the event loop only


def enabled() -> bool:
    return os.environ.get("WARM_CACHE", "0") == "1"


def first_urls(topics: list[dict]) -> list[str]:
    out = ["/api/check/recorded", "/api/stats"]
    for t in topics:
        out.append(f"/api/compare?topic={t['topic_id']}&limit={PAGE}&offset=0")
        out.append(f"/api/dropped?topic={t['topic_id']}&limit={PAGE}&offset=0")
    return out


async def warm(app) -> int:
    """Ask for the first pages of every topic, then the further Differences pages, then the same for the quick picks
    of the date button. Returns the requests made."""
    n = 0
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://warm", timeout=300) as client:
        r = await client.get("/api/topics")
        n += 1
        if r.status_code != 200:
            return n
        topics = r.json().get("topics", [])
        past = [
            f"/api/compare?topic={t['topic_id']}&as_of={d}&limit={PAGE}&offset=0" for d in PICK_DATES for t in topics
        ]
        for urls in (first_urls(topics), past):
            later: list[str] = []
            for url in urls:
                r = await client.get(url)
                n += 1
                if r.status_code == 200 and url.startswith("/api/compare"):
                    total = int(r.json().get("total_rows") or 0)
                    base = url.rsplit("&offset=", 1)[0]
                    later += [f"{base}&offset={o}" for o in range(PAGE, total, PAGE)]
            for url in later:
                await client.get(url)
                n += 1
    return n


def start(app, loop: asyncio.AbstractEventLoop | None = None) -> None:
    """Warm in the background on `loop` (any thread may call this, e.g. the ingest worker after a job)."""
    if not enabled():
        return

    async def run() -> None:
        if _state["running"]:  # an ingest calls this after every edition: one warm-up at a time, then once more
            _state["again"] = True
            return
        _state["running"] = True
        try:
            while True:
                _state["again"] = False
                try:
                    log.info("cache warmed with %d requests", await warm(app))
                except Exception as e:  # best effort, a visitor's own request does the same work
                    log.warning("cache warm-up stopped: %s", e)
                if not _state["again"]:
                    break
        finally:
            _state["running"] = False

    if loop is None:
        asyncio.get_running_loop().create_task(run())
    else:
        loop.call_soon_threadsafe(lambda: loop.create_task(run()))
