import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pipeline import wapi


class _Handler(BaseHTTPRequestHandler):
    hits: list[str] = []
    plan: list[tuple[int, dict]] = []

    def do_GET(self):  # noqa: N802
        type(self).hits.append(self.path)
        status, headers = type(self).plan.pop(0) if type(self).plan else (200, {})
        body = json.dumps({"ok": True, "path": self.path}).encode()
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(wapi, "CACHE_DIR", tmp_path / "raw")
    wapi.reset_stats()
    _Handler.hits = []
    _Handler.plan = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_user_agent_names_project_and_requests():
    ua = wapi.SESSION.headers["User-Agent"]
    assert ua.startswith("Parallax/0.1 (https://github.com/timkicker/attention-is-all-we-have) python-requests/")


def test_429_then_200_then_cache_hit(server):
    _Handler.plan = [(429, {"Retry-After": "1"}), (200, {})]
    url = f"{server}/w/api.php"
    first = wapi.get(url, {"action": "query", "titles": "Talvisota"})
    assert first["ok"] is True
    assert len(_Handler.hits) == 2
    assert wapi.STATS["r429"] == 1
    assert wapi.STATS["wait_s"] >= 1
    assert "maxlag=5" in _Handler.hits[-1]

    calls_before = wapi.STATS["calls"]
    second = wapi.get(url, {"titles": "Talvisota", "action": "query"})  # same params, other order
    assert second == first
    assert len(_Handler.hits) == 2
    assert wapi.STATS["calls"] == calls_before
    assert wapi.STATS["hits"] == 1


def test_5xx_retried_then_ok(server):
    _Handler.plan = [(503, {}), (200, {})]
    wapi.get(f"{server}/w/api.php", {"action": "query", "x": "1"}, backoff=0)
    assert len(_Handler.hits) == 2
    assert wapi.STATS["r5xx"] == 1


def test_5xx_gives_up_after_three_retries(server):
    _Handler.plan = [(500, {})] * 4
    with pytest.raises(wapi.WikiError):
        wapi.get(f"{server}/w/api.php", {"action": "query", "x": "2"}, backoff=0)
    assert len(_Handler.hits) == 4


def test_non_action_api_has_no_maxlag(server):
    wapi.get(f"{server}/api/rest_v1/page/html/X", {})
    assert "maxlag" not in _Handler.hits[-1]


def test_parallel_capped_at_three(monkeypatch):
    monkeypatch.setenv("WIKI_PARALLEL", "10")
    assert wapi.parallel_limit() == 3
    monkeypatch.setenv("WIKI_PARALLEL", "2")
    assert wapi.parallel_limit() == 2
    monkeypatch.delenv("WIKI_PARALLEL")
    assert wapi.parallel_limit() == 1


def test_no_write_actions():
    with pytest.raises(ValueError):
        wapi.get("https://fi.wikipedia.org/w/api.php", {"action": "edit"})


def test_max_age_zero_neither_reads_nor_writes_the_cache(monkeypatch):
    class Resp:
        status_code = 200
        headers: dict = {}

        @staticmethod
        def json():
            return {"batchcomplete": True}

    monkeypatch.setattr(wapi.SESSION, "get", lambda *a, **k: Resp())
    params = {"action": "query", "list": "search", "srsearch": "never kept"}
    wapi.get("https://example.invalid/w/api.php", params, max_age_s=0)
    key = wapi.cache_key("https://example.invalid/w/api.php", {**params, "format": "json", "maxlag": 5})
    assert not wapi._cache_path(key).exists()


def _answers(monkeypatch, *resps):
    """SESSION.get answers with resps in turn; returns the list of sleeps."""
    queue = list(resps)
    slept: list[float] = []
    monkeypatch.setattr(wapi.SESSION, "get", lambda *a, **k: queue.pop(0))
    monkeypatch.setattr(wapi.time, "sleep", slept.append)
    monkeypatch.setattr(wapi, "_cooldown_until", 0.0)
    return slept


class _Resp:
    def __init__(self, status: int, headers: dict | None = None, body: dict | None = None) -> None:
        self.status_code, self.headers, self._body = status, headers or {}, body or {"batchcomplete": True}

    def json(self):
        return self._body


MAXLAG = {"error": {"code": "maxlag", "info": "Waiting for a replica"}}


def _interactive(x: str) -> dict:
    return wapi.get("https://example.invalid/w/api.php", {"action": "query", "x": x}, max_age_s=0, interactive=True)


def test_interactive_call_passes_a_long_retry_after_on_at_once(monkeypatch):
    slept = _answers(monkeypatch, _Resp(429, {"Retry-After": "30"}))
    with pytest.raises(wapi.RateLimited) as e:
        _interactive("long")
    assert slept == [] and e.value.retry_after_s == 30
    assert 25 < wapi.cooldown_left() <= 30  # Wikimedia said so: everyone waits that long
    monkeypatch.setattr(wapi, "_cooldown_until", 0.0)


def test_interactive_call_retries_once(monkeypatch):
    slept = _answers(monkeypatch, _Resp(429), _Resp(200))
    assert _interactive("again") == {"batchcomplete": True}
    assert slept == [wapi.INTERACTIVE_RETRY_S] and wapi.cooldown_left() == 0


def test_interactive_maxlag_sets_no_cooldown(monkeypatch):
    slept = _answers(monkeypatch, _Resp(200, body=MAXLAG), _Resp(200, body=MAXLAG))
    with pytest.raises(wapi.RateLimited):
        _interactive("lag")
    assert len(slept) == 1 and wapi.cooldown_left() == 0


def test_interactive_429_without_retry_after_sets_no_cooldown(monkeypatch):
    _answers(monkeypatch, _Resp(429), _Resp(429))
    with pytest.raises(wapi.RateLimited):
        _interactive("bare")
    assert wapi.cooldown_left() == 0


def test_batch_call_keeps_retrying(monkeypatch):
    slept = _answers(monkeypatch, *[_Resp(200, body=MAXLAG)] * 3, _Resp(200))
    body = wapi.get("https://example.invalid/w/api.php", {"action": "query", "x": "batch"}, max_age_s=0)
    assert body == {"batchcomplete": True} and len(slept) == 3


def test_command_line_ingest_asks_wikidata_with_retries(monkeypatch):
    from pipeline import job, wikidata

    seen = []
    monkeypatch.setattr(wikidata, "entity", lambda qid, interactive=True: seen.append(interactive))

    class Cur:  # no topic, no job, no job running
        description = None

        def execute(self, sql, params=()):
            self.description = [("n",)] if "COUNT" in sql else None

        def fetchall(self):
            return [(0,)] if self.description else []

    with pytest.raises(job.UnknownItem):
        job._create(Cur(), "Q90000099", None, None, None)  # the command line: no cap
    with pytest.raises(job.UnknownItem):
        job._create(Cur(), "Q90000099", None, None, 4)  # the API
    assert seen == [False, True]


def test_network_error_becomes_wiki_error(monkeypatch):
    def down(*a, **k):
        raise wapi.requests.ConnectionError("down")

    monkeypatch.setattr(wapi.SESSION, "get", down)
    try:
        wapi.get("https://example.invalid/w/api.php", {"action": "query", "x": "down"}, interactive=True)
    except wapi.WikiError:
        pass
    else:
        raise AssertionError("no WikiError")
