import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from validio.config import load_settings
from validio.valio.budget import CallBudget, CallBudgetExceeded
from validio.valio.client import ReplayMiss, ValioClient

BASE = "https://junction26.valioaimo.fi"
MON = date(2026, 11, 16)


def price_body(ids):
    return {"customerId": "hotel-espoo", "currency": "EUR", "pricingDate": "2026-11-16T00:00:00+0200",
            "products": [{"productId": i, "quantity": 1.0, "netPriceFound": False, "error": True} for i in ids]}


def echo_price(request):
    return httpx.Response(200, json=price_body(json.loads(request.content)["products"]))


@pytest.fixture
def recorded():
    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip(f"needs_data: no recorded Valio answers in {s.valio_cache}, run make record")
    return ValioClient(s.valio_base_url, "", "replay", s.valio_cache)


# facts from the recorded answers of the live test API


def test_price_464306_net_price(recorded):
    q = recorded.price(["464306"], MON, CallBudget(40))["464306"]
    assert not q.error
    assert q.price_cents == 101
    assert q.valid_to == date(2026, 12, 31)


def test_463038_terminal_999999(recorded):
    a = recorded.availability(["463038"], MON, CallBudget(40))["463038"]
    assert a.logistic_model == "Terminal"
    assert a.amount == 999999


def test_473986_has_no_lines(recorded):
    a = recorded.availability(["473986"], MON, CallBudget(40))["473986"]
    assert a.lines == []
    assert not a.deliverable


def test_463968_stock_137(recorded):
    a = recorded.availability(["463968"], MON, CallBudget(40))["463968"]
    assert (a.logistic_model, a.amount, a.lines[0].sales_unit) == ("Stock", 137, "ST")


def test_471376_stock_27(recorded):
    a = recorded.availability(["471376"], MON, CallBudget(40))["471376"]
    assert (a.logistic_model, a.amount, a.lines[0].sales_unit) == ("Stock", 27, "KI")


def test_unknown_product_error_flag(recorded):
    q = recorded.price(["999999999"], MON, CallBudget(40))["999999999"]
    assert q.error
    assert q.price_cents is None


# client mechanics, no network


def test_budget_blocks_41_ids():
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(f"{BASE}/api/price").mock(side_effect=echo_price)
        c = ValioClient(BASE, "k", "live", None)
        b = CallBudget(40)
        with pytest.raises(CallBudgetExceeded):
            c.price([str(460000 + i) for i in range(41)], MON, b)
        assert route.call_count == 0
        assert b.calls == 0 and b.ids_sent == 0


def test_budget_counts_distinct_ids_per_request():
    with respx.mock() as mock:
        mock.post(f"{BASE}/api/price").mock(side_effect=echo_price)
        c = ValioClient(BASE, "k", "live", None)
        b = CallBudget(40)
        ids = [str(460000 + i) for i in range(30)]
        c.price(ids, MON, b)
        c.price(ids, MON, b)  # the same ids again cost nothing new
        assert (b.calls, b.ids_sent) == (2, 30)
        with pytest.raises(CallBudgetExceeded):
            c.price([str(470000 + i) for i in range(11)], MON, b)


def test_chunks_over_1000():
    with respx.mock() as mock:
        route = mock.post(f"{BASE}/api/price").mock(side_effect=echo_price)
        c = ValioClient(BASE, "k", "live", None)
        out = c.price([str(400000 + i) for i in range(2001)], MON, CallBudget(5000))
        assert len(out) == 2001
        sizes = [len(json.loads(call.request.content)["products"]) for call in route.calls]
        assert sizes == [1000, 1000, 1]


def test_sends_key_and_customer():
    with respx.mock() as mock:
        route = mock.post(f"{BASE}/api/price").mock(side_effect=echo_price)
        ValioClient(BASE, "secret", "live", None, customer="hotel-espoo").price(["464306"], MON, CallBudget(40))
        req = route.calls[0].request
        assert req.headers["X-API-Key"] == "secret"
        assert json.loads(req.content) == {"customer": "hotel-espoo", "requestedDate": "2026-11-16",
                                           "products": ["464306"]}


def test_record_then_replay_never_calls_network(tmp_path):
    with respx.mock() as mock:
        mock.post(f"{BASE}/api/price").mock(side_effect=echo_price)
        ValioClient(BASE, "k", "record", tmp_path).price(["1", "2", "3"], MON, CallBudget(40))
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route()  # any request at all would hit this
        c = ValioClient(BASE, "", "replay", tmp_path)
        b = CallBudget(40)
        assert set(c.price(["3", "1"], MON, b)) == {"1", "3"}  # a subset replays from the recorded call
        assert b.ids_sent == 2
        with pytest.raises(ReplayMiss):
            c.price(["4"], MON, CallBudget(40))
        assert route.call_count == 0


def test_replay_never_calls_network(recorded):
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route()
        recorded.price(["464306", "463038"], MON, CallBudget(40))
        recorded.availability(["464306", "463038"], MON, CallBudget(40))
        assert route.call_count == 0


def test_forbidden_host_refused():
    with pytest.raises(ValueError):
        ValioClient("https://api.valioaimo" + ".fi", "k", "live", None)


@pytest.mark.live
def test_live_ping():
    s = load_settings()
    from validio.valio.client import checked_base_url

    r = httpx.get(checked_base_url(s.valio_base_url) + "/api/ping", headers={"X-API-Key": s.valio_api_key}, timeout=30)
    assert r.json() == {"status": "ok"}


# The guard parses the URL: only https://junction26.valioaimo.fi, in any letter case, no userinfo (review M2).
BAD_BASES = [
    "https://API.valioaimo" + ".fi",
    "https://u@api.valioaimo" + ".fi",
    "https://TOIMITUSTUKKU.valioaimo" + ".fi",
    "https://www.valioaimo.fi",
    "http://junction26.valioaimo.fi",
    "https://junction26.valioaimo.fi.evil.example",
    "https://user:pw@junction26.valioaimo.fi",
    "https://junction26.valioaimo.fi:8443",
    "junction26.valioaimo.fi",
]


@pytest.mark.parametrize("base", BAD_BASES)
def test_only_the_test_api_host(base):
    from validio.valio.client import checked_base_url

    with pytest.raises(ValueError, match="only https://junction26.valioaimo.fi"):
        checked_base_url(base)
    with pytest.raises(ValueError, match="only https://junction26.valioaimo.fi"):
        ValioClient(base, "k", "live", None)


def test_test_api_host_accepted():
    from validio.valio.client import checked_base_url

    assert checked_base_url("https://Junction26.ValioAimo.fi/") == "https://junction26.valioaimo.fi"
    assert ValioClient("https://junction26.valioaimo.fi", "k", "live", None).base_url == \
        "https://junction26.valioaimo.fi"


def test_fetch_data_refuses_other_hosts(tmp_path, monkeypatch):
    import importlib.util

    script = Path(__file__).resolve().parents[3] / "scripts" / "fetch_data.py"
    spec = importlib.util.spec_from_file_location("fetch_data", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv("VALIO_BASE_URL", "https://API.valioaimo" + ".fi")
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: pytest.fail("a request went out"))
    monkeypatch.setattr("sys.argv", ["fetch_data.py", "--out", str(tmp_path)])
    with pytest.raises(ValueError, match="only https://junction26.valioaimo.fi"):
        mod.main()


def test_replay_refuses_recordings_that_disagree(tmp_path):
    d = tmp_path / "price" / MON.isoformat()
    d.mkdir(parents=True)
    row = {"productId": "464306", "error": False, "catalogPrice": {"value": 1.01}}
    for i, value in enumerate((1.01, 1.50)):
        resp = {"timeNow": "2026-11-14T10:00:00+0200", "products": [{**row, "catalogPrice": {"value": value}},
                                                                  {**row, "productId": f"9{i}"}]}
        (d / f"{i}.json").write_text(json.dumps({"response": resp}))
    client = ValioClient("https://junction26.valioaimo.fi", "", "replay", tmp_path)
    with pytest.raises(ReplayMiss, match="recordings disagree"):
        client.price(["464306"], MON, CallBudget(40))
    assert client.price(["90"], MON, CallBudget(40))["90"].price_cents == 101  # control: no conflict
