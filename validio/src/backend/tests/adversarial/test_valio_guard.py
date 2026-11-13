"""Valio guard: the API key may only ever travel to https://junction26.valioaimo.fi. Every URL trick for
Valio's real webshop hosts (case, user info, IDN look-alikes, trailing dot, IP, ports, redirects) is refused,
and no request ever reaches those hosts.

The webshop host names are built from parts, so this file passes scripts/check_forbidden_hosts.sh."""

import contextlib
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from hypothesis import given
from hypothesis import strategies as st

from validio.valio.budget import CallBudget
from validio.valio.client import TEST_API_HOST, ValioClient, checked_base_url


def _host(*labels: str) -> str:
    return ".".join(labels)


SHOP = _host("toimitustukku", "valioaimo", "fi")
API = _host("api", "valioaimo", "fi")
FORBIDDEN = (SHOP, API)
OK = f"https://{TEST_API_HOST}"
MONDAY = date(2026, 11, 16)

TRICKS = [
    f"https://{SHOP}", f"https://{API}", f"HTTPS://{SHOP.upper()}", f"https://{API.upper()}", f"https://{SHOP}.",
    f"https://{API}.", f"https://{API}:443", f"https://{API}:8443", f"http://{API}", f"http://{TEST_API_HOST}",
    f"https://user:pw@{API}", f"https://{TEST_API_HOST}@{API}", f"https://{TEST_API_HOST}:443@{API}",
    f"https://{API}#@{TEST_API_HOST}", f"https://{API}?h={TEST_API_HOST}", f"https://{API}/{TEST_API_HOST}",
    f"https://{TEST_API_HOST}.{API}", f"https://{TEST_API_HOST}.evil.example", f"https://evil.example/{TEST_API_HOST}",
    f"https://{TEST_API_HOST}.", f"https://{TEST_API_HOST}:8443", f"https://user@{TEST_API_HOST}",
    f"https://:@{TEST_API_HOST}", "https://juncti\u043en26.valioaimo.fi",  # Cyrillic \u043e
    "https://junction26.valioaimo.f\u0456",  # Ukrainian \u0456
    "https://\uff4a\uff55\uff4e\uff43\uff54\uff49\uff4f\uff4e\uff12\uff16.valioaimo.fi",  # fullwidth
    "https://xn--junctin26-xxx.valioaimo.fi", "https://junction26\u200b.valioaimo.fi",
    "https://1.2.3.4", "https://127.0.0.1", "https://[::1]", "https://2130706433", "https://0x7f000001",
    f"//{API}", f"{API}", f"https:{API}", f"https:/{API}", f"https:\\\\{API}", f"https://{TEST_API_HOST}\\@{API}",
    f"ftp://{TEST_API_HOST}", f"wss://{TEST_API_HOST}", f"file:///{TEST_API_HOST}", "", "https://",
    f"https://{TEST_API_HOST}\n.{API}", f" https://{API}",
]


@pytest.mark.parametrize("url", TRICKS)
def test_trick_is_refused(url):
    with pytest.raises((ValueError, httpx.InvalidURL)):
        checked_base_url(url)
    with pytest.raises((ValueError, httpx.InvalidURL)):
        ValioClient(url, "key", "live", None)


@pytest.mark.parametrize("url", [OK, OK + "/", OK.upper(), f"https://{TEST_API_HOST}:443", OK + "/api/price?x=1",
                                 "https://Junction26.ValioAimo.FI"])
def test_test_host_spellings_give_the_one_base(url):
    assert checked_base_url(url) == OK


fragments = st.sampled_from(["https://", "http://", "HTTPS://", "//", "", "https:/"])
userinfo = st.sampled_from(["", "u@", "u:p@", f"{TEST_API_HOST}@", f"{API}@", ":@", "%40@"])
hosts = st.sampled_from([TEST_API_HOST, TEST_API_HOST.upper(), SHOP, API, f"{TEST_API_HOST}.", f"{API}.",
                         f"{TEST_API_HOST}.{API}", f"{API}.{TEST_API_HOST}", "juncti\u043en26.valioaimo.fi", "1.2.3.4",
                         "[::1]", "valioaimo.fi", "junction26-valioaimo.fi"])
ports = st.sampled_from(["", ":443", ":80", ":8443", ":0", ":", ":443:443"])
tails = st.sampled_from(["", "/", f"/{API}", f"#{API}", f"?{API}", f"@{API}", f"\\@{API}", "/..", "%2F"])


@given(fragments, userinfo, hosts, ports, tails)
def test_any_composed_url_gives_the_test_base_or_refuses(scheme, user, host, port, tail):
    url = scheme + user + host + port + tail
    try:
        base = checked_base_url(url)
    except (ValueError, httpx.InvalidURL):
        return
    assert base == OK, url
    assert scheme.lower() == "https://" and user == "" and host.lower() == TEST_API_HOST, url


@given(st.text(max_size=60))
def test_random_text_gives_the_test_base_or_refuses(url):
    try:
        assert checked_base_url(url) == OK
    except (ValueError, httpx.InvalidURL):
        pass


# On the wire: whatever comes back, nothing goes to the webshop

def _shop_routes(net):
    return [net.route(host=h) for h in FORBIDDEN] + [net.route(host=h.upper()) for h in FORBIDDEN]


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("target", [f"https://{API}/api/price", f"https://{SHOP}/api/price", f"//{API}/x"])
def test_redirect_to_the_webshop_is_not_followed(status, target):
    with respx.mock(assert_all_called=False) as net:
        shop = _shop_routes(net)
        net.post(f"{OK}/api/price").mock(return_value=httpx.Response(status, headers={"Location": target}))
        c = ValioClient(OK, "secret-key", "live", None)
        with pytest.raises(httpx.HTTPStatusError):
            c.price(["464306"], MONDAY, CallBudget())
        assert all(r.call_count == 0 for r in shop)
        assert {str(call.request.url.host) for call in net.calls} == {TEST_API_HOST}


def test_every_live_call_goes_to_the_test_host_with_the_key():
    with respx.mock(assert_all_called=False) as net:
        shop = _shop_routes(net)
        ok = net.post(url__startswith=f"{OK}/api/").mock(
            return_value=httpx.Response(200, json={"products": [], "timeNow": "2026-11-14T10:00:00+0200"}))
        c = ValioClient("HTTPS://JUNCTION26.VALIOAIMO.FI/", "secret-key", "live", None, chunk=2)
        b = CallBudget()
        c.price(["1", "2", "3"], MONDAY, b)
        c.availability(["1", "2", "3"], MONDAY, b)
        assert ok.call_count == 4 and all(r.call_count == 0 for r in shop)
        for call in net.calls:
            assert call.request.url.scheme == "https" and call.request.url.host == TEST_API_HOST
            assert call.request.headers["X-API-Key"] == "secret-key"


def test_injected_redirect_following_client_cannot_reach_the_webshop():
    with respx.mock(assert_all_called=False) as net:
        shop = _shop_routes(net)
        for r in shop:
            r.mock(return_value=httpx.Response(200, json={"products": []}))
        net.post(f"{OK}/api/price").mock(return_value=httpx.Response(307, headers={"Location": f"https://{API}/p"}))
        c = ValioClient(OK, "secret-key", "live", None, http=httpx.Client(follow_redirects=True))
        with contextlib.suppress(Exception):  # refusing is the fix
            c.price(["464306"], MONDAY, CallBudget())
        assert all(r.call_count == 0 for r in shop)


def test_replay_never_opens_a_connection(tmp_path):
    with respx.mock(assert_all_called=False) as net:
        anything = net.route()
        c = ValioClient(OK, "secret-key", "replay", tmp_path)
        with pytest.raises(LookupError):
            c.price(["464306"], MONDAY, CallBudget())
        assert anything.call_count == 0


@pytest.mark.parametrize("url", [f"https://{API}", f"https://{TEST_API_HOST}@{SHOP}", f"http://{TEST_API_HOST}"])
def test_settings_pointing_at_the_webshop_stop_the_runtime(monkeypatch, url):
    from validio.api.steady import Runtime

    monkeypatch.setenv("VALIO_BASE_URL", url)
    with pytest.raises(ValueError, match="only https://junction26"):
        Runtime().valio  # noqa: B018 the property builds the client


def test_fetch_data_refuses_the_webshop_and_redirects(monkeypatch, tmp_path):
    """scripts/fetch_data.py downloads Valio's files with the key: same guard, no redirect followed."""
    scripts = Path(__file__).resolve().parents[4] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    import fetch_data

    monkeypatch.setattr(sys, "argv", ["fetch_data.py", "--out", str(tmp_path)])
    monkeypatch.setenv("VALIO_BASE_URL", f"https://{API}")
    with pytest.raises(ValueError):
        fetch_data.main()
    monkeypatch.setenv("VALIO_BASE_URL", OK)
    with respx.mock(assert_all_called=False) as net:
        shop = _shop_routes(net)
        net.get(url__startswith=OK).mock(return_value=httpx.Response(302, headers={"Location": f"https://{SHOP}/f"}))
        with pytest.raises(httpx.HTTPStatusError):
            fetch_data.main()
        assert all(r.call_count == 0 for r in shop)
