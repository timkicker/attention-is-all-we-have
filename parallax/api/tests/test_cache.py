import asyncio

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


def test_a_write_clears_the_cache(client):
    client.get("/api/topics")
    assert cache._store
    client.post("/api/check", json={"text": "Talvisota alkoi 30. marraskuuta 1939.", "lang": "fi"})
    assert not cache._store


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
