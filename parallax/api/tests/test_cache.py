import asyncio
import re

import pytest

from api import cache, sqllog


def _statement_count(client, path: str) -> int:
    return len(client.get(path).json()["sql"])


def test_a_repeated_get_is_served_from_the_cache(client, monkeypatch):
    calls = []
    real = sqllog.run
    monkeypatch.setattr(sqllog, "run", lambda *a, **k: calls.append(1) or real(*a, **k))
    first = client.get("/api/topics")
    n = len(calls)
    second = client.get("/api/topics")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()  # the same body, `sql` included
    assert len(calls) == n  # no statement ran for the second request
    client.get("/api/topics?x=1")
    assert len(calls) > n  # another query string is another key


def test_progress_errors_and_sql_panels_are_not_cached(client):
    assert (
        cache.key(type("R", (), {"method": "GET", "url": type("U", (), {"path": "/api/ingest/Q1", "query": ""})})())
        is None
    )
    client.get("/api/compare?topic=nope")
    assert not any(k.startswith("/api/compare") for k in cache._store)


def test_a_check_keeps_the_cache_an_ingest_write_clears_it(client):
    client.get("/api/topics")
    assert cache._store
    r = client.post("/api/check", json={"text": "Talvisota alkoi 30. marraskuuta 1939.", "topic": "winterwar"})
    assert r.status_code == 200
    assert cache._store  # a check only adds its own run, the warm pages of other visitors stay


def test_an_ingest_clears_its_own_topic_only(client):
    from api.main import data_changed
    from api.routes import dropped

    for url in ("/api/topics", "/api/compare?topic=winterwar", "/api/dropped?topic=winterwar"):
        assert client.get(url).status_code == 200
    gen = cache.generation()
    data_changed("q122100")  # another article stored an edition
    assert cache.get("/api/compare?topic=winterwar") is not None  # the demo article stays warm
    assert cache.get("/api/dropped?topic=winterwar") is not None
    assert cache.get("/api/topics?") is None  # the article list shows the new one
    assert any(k[0] == "winterwar" for k in dropped._CACHE)
    cache.put("/api/compare?topic=q122100", gen, b"{}", {}, None, [])  # computed before the ingest stored data
    assert cache.get("/api/compare?topic=q122100") is None
    data_changed("WinterWar")
    assert cache.get("/api/compare?topic=winterwar") is None


def test_a_cached_answer_is_gzip_once_with_an_etag_and_a_304(client):
    first = client.get("/api/topics")
    second = client.get("/api/topics", headers={"Accept-Encoding": "gzip"})
    assert second.headers["content-encoding"] == "gzip"
    assert second.json() == first.json()  # the client decompresses it
    etag = second.headers["etag"]
    assert etag and second.headers["cache-control"] == "no-cache"
    again = client.get("/api/topics", headers={"If-None-Match": etag})
    assert again.status_code == 304 and not again.content
    plain = client.get("/api/topics", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers and plain.json() == first.json()


def test_warm_up_fills_the_cache_with_the_first_pages(client):
    from api import warm
    from api.main import app

    cache.clear()
    n = asyncio.run(warm.warm(app))
    assert n > 3
    assert "/api/compare?topic=winterwar&limit=200&offset=0" in cache._store
    assert "/api/dropped?topic=winterwar&limit=200&offset=0" in cache._store
    # the quick picks of the date button, with the query the web app sends (src/lib/adapt/topic.ts)
    assert "/api/compare?topic=winterwar&as_of=2015-01-01&limit=200&offset=0" in cache._store


def test_warmed_dates_are_the_quick_picks_of_the_date_button():
    from pathlib import Path

    from api import warm

    svelte = (Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "ui" / "AsOf.svelte").read_text()
    (picks,) = re.findall(r"picks = \[null, ([^\]]*)\]", svelte)
    assert tuple(re.findall(r"'([0-9-]+)'", picks)) == warm.PICK_DATES


def test_a_result_computed_across_a_clear_is_not_stored():
    gen = cache.generation()
    cache.clear()
    cache.put("/api/x?", gen, b"{}", {}, None, [])
    assert cache.get("/api/x?") is None


def test_concurrent_misses_compute_once():
    runs = []

    async def visitor():
        async with cache.single_flight("/api/y?"):
            if cache.get("/api/y?") is None:
                runs.append(1)
                await asyncio.sleep(0.01)
                cache.put("/api/y?", cache.generation(), b"{}", {}, None, [])

    async def main():
        await asyncio.gather(*[visitor() for _ in range(20)])

    asyncio.run(main())
    assert len(runs) == 1
    assert not cache._locks


def test_cold_differences_pages_run_a_few_at_a_time(monkeypatch):
    # A room picking dates at once: each cold page is seconds of exact search. The others wait without a thread.
    import httpx

    from api import main

    running, most = [0], [0]

    async def slow(request, call_next):
        running[0] += 1
        most[0] = max(most[0], running[0])
        await asyncio.sleep(0.05)
        running[0] -= 1
        return main.Response(b"{}", media_type="application/json"), None, [], b"{}"

    monkeypatch.setattr(main, "_with_sql", slow)
    monkeypatch.setattr(main, "_HEAVY", asyncio.Semaphore(2))

    async def go():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            dates = [f"20{y:02d}-01-01" for y in range(10, 16)]
            await asyncio.gather(*(c.get(f"/api/compare?topic=heavy&as_of={d}") for d in dates))
            assert most[0] == 2
            most[0] = 0
            await asyncio.gather(*(c.get(f"/api/compare?topic=heavy&h=h{i}") for i in range(6)))  # one statement
            assert most[0] == 6

        # Under the hood's live query does not wait behind cold pages
        assert not main._heavy(httpx.Request("GET", "http://t/api/sql/vector?topic=winterwar"))

    cache.clear()
    asyncio.run(go())
    cache.clear()


def test_the_page_shell_answers_head_and_get(client):
    from api import main

    if not main.DIST.is_dir():
        pytest.skip("no web build (make web-build)")
    assert client.head("/t/winterwar").status_code == 200
    r = client.get("/t/winterwar")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html") and b"<div" in r.content
