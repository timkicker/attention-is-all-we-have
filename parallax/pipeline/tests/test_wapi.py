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
