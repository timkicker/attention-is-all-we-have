"""Spend Pass fuzzing: mutated bytes, forged disclosures and key-binding JWTs, alg none, key confusion,
odd validity windows and replayed nonces, at the verifier and over MCP and /agent/v1. Every case must be
refused with a MandateError (HTTP 401) whose message says why."""

import base64
import hashlib
import hmac
import json
import threading
from datetime import datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS

from validio.policy.mandate import (
    AUDIENCE,
    DEMO_CLAIMS,
    DEMO_SD_FIELDS,
    MandateError,
    NonceStore,
    issue_mandate,
    present,
    verify_presentation,
)

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
SHOWN = {"autoLimitCents", "hardCapCents", "diet"}
ISSUER = DEMO_CLAIMS["iss"]
IAT = int(NOW.timestamp())

# Every reason the verifier may give. "invalid Spend Pass (...)" names the parser error class.
REASONS = ("no key binding", "unknown or reused nonce", "stale nonce", "wrong algorithm",
           "issuer signature does not verify", "unknown issuer", "holder key binding does not verify",
           "wrong audience", "disclosures do not match the key binding", "Spend Pass without validity window",
           "Spend Pass not valid yet", "Spend Pass expired", "money must be whole cents", "invalid Spend Pass (",
           "disclosure not part of the Spend Pass", "key binding signed at the wrong time",
           "Spend Pass issued in the future")

KITCHEN = JWK.generate(kty="EC", crv="P-256")
AGENT = JWK.generate(kty="EC", crv="P-256")
MALLORY = JWK.generate(kty="EC", crv="P-256")
ISSUANCE = issue_mandate(DEMO_CLAIMS, DEMO_SD_FIELDS, KITCHEN, AGENT)


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def b64j(obj) -> str:
    return b64(json.dumps(obj, separators=(",", ":")).encode())


def unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def jws(header: dict, payload: dict, key: JWK | None) -> str:
    """A compact JWS with exactly this protected header. key=None gives an empty signature."""
    if key is None:
        return f"{b64j(header)}.{b64j(payload)}."
    s = JWS(json.dumps(payload, separators=(",", ":")).encode())
    s.add_signature(key, alg=header["alg"], protected=json.dumps(header))
    return s.serialize(compact=True)


def sd_hash(issuer_jwt: str, disclosures: list[str]) -> str:
    return b64(hashlib.sha256("~".join([issuer_jwt, *disclosures, ""]).encode()).digest())


def kb(issuer_jwt: str, disclosures: list[str], nonce: str, *, key=AGENT, alg="ES256", typ="kb+jwt",
       aud=AUDIENCE, iat: int | None = None, drop: tuple[str, ...] = ()) -> str:
    payload = {"nonce": nonce, "aud": aud, "iat": int(NOW.timestamp()) if iat is None else iat,
               "sd_hash": sd_hash(issuer_jwt, disclosures)}
    payload = {k: v for k, v in payload.items() if k not in drop}
    return jws({"alg": alg, "typ": typ}, payload, key)


def honest_parts(nonces: NonceStore, issuance=ISSUANCE, disclose=SHOWN):
    nonce = nonces.issue(NOW)
    token = present(issuance, disclose, AGENT, AUDIENCE, nonce, IAT)
    jwt, *disc, kbjwt = token.split("~")
    return nonce, jwt, disc, kbjwt


def verify(token: str, nonces: NonceStore, now=NOW, kitchen=KITCHEN):
    return verify_presentation(token, kitchen_pub=kitchen, issuer=ISSUER, aud=AUDIENCE, nonces=nonces, now=now)


def refused(token: str, nonces: NonceStore, now=NOW) -> str:
    with pytest.raises(MandateError) as e:
        verify(token, nonces, now)
    msg = str(e.value)
    assert msg.startswith(REASONS), msg
    assert "eyJ" not in msg, "the reason must never echo the token"
    return msg


def test_honest_presentation_is_accepted():
    nonces = NonceStore()
    nonce, jwt, disc, _ = honest_parts(nonces)
    m = verify("~".join([jwt, *disc, kb(jwt, disc, nonce)]), nonces)
    assert (m.auto_limit_cents, m.hard_cap_cents) == (120000, 200000)


# Random byte mutations

B64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def _same_decoded(a: str, b: str) -> bool:
    """Two tokens whose segments decode to the same bytes (base64url ignores unused trailing bits)."""
    def segs(t):
        out = []
        for part in t.split("~"):
            for s in part.split("."):
                try:
                    out.append(unb64(s))
                except ValueError:
                    out.append(s.encode())
        return out
    return segs(a) == segs(b)


@given(st.data())
def test_any_single_mutation_is_refused(data):
    nonces = NonceStore()
    token = present(ISSUANCE, SHOWN, AGENT, AUDIENCE, nonces.issue(NOW), IAT)
    i = data.draw(st.integers(0, len(token) - 1), label="position")
    op = data.draw(st.sampled_from(["replace", "delete", "insert", "swap"]), label="op")
    ch = data.draw(st.sampled_from(B64_CHARS + "~.=+/ \x00é"), label="char")
    if op == "replace":
        bad = token[:i] + ch + token[i + 1:]
    elif op == "delete":
        bad = token[:i] + token[i + 1:]
    elif op == "insert":
        bad = token[:i] + ch + token[i:]
    else:
        j = data.draw(st.integers(0, len(token) - 1), label="other")
        lst = list(token)
        lst[i], lst[j] = lst[j], lst[i]
        bad = "".join(lst)
    if bad == token or _same_decoded(bad, token):
        return
    try:
        verify(bad, nonces)
    except MandateError as e:
        assert str(e).startswith(REASONS), str(e)
        return
    pytest.fail(f"a mutated Spend Pass was accepted ({op} {ch!r} at {i})")


@given(st.lists(st.sampled_from(["drop", "dup", "shuffle", "forge", "garble"]), min_size=1, max_size=3),
       st.randoms(use_true_random=False))
def test_disclosure_list_mutations_are_refused(ops, rnd):
    """The holder re-signs its own key binding over whatever disclosure list it wants. It may hide fields,
    never show a field the kitchen did not sign or show one twice."""
    nonces = NonceStore()
    nonce, jwt, disc, _ = honest_parts(nonces)
    orig = list(disc)
    for op in ops:
        if op == "drop" and disc:
            disc.pop(rnd.randrange(len(disc)))
        elif op == "dup" and disc:
            disc.insert(rnd.randrange(len(disc) + 1), rnd.choice(disc))
        elif op == "shuffle":
            rnd.shuffle(disc)
        elif op == "forge":
            disc.append(b64j([b64(rnd.randbytes(16)), "autoLimitCents", 10**9]))
        elif op == "garble":
            disc.append(b64(rnd.randbytes(rnd.randrange(1, 40))))
    token = "~".join([jwt, *disc, kb(jwt, disc, nonce)])
    try:
        m = verify(token, nonces)
    except MandateError as e:
        assert str(e).startswith(REASONS), str(e)
        return
    # accepted: never with a disclosure shown twice, and never with a value the kitchen did not sign.
    # (An extra, unreferenced disclosure is accepted and ignored today: G4, test_unreferenced_disclosure_*.)
    assert len(disc) == len(set(disc)), "a doubled disclosure was accepted"
    assert m.auto_limit_cents in (None, 120000) and m.hard_cap_cents in (None, 200000)
    assert set(m.disclosed) <= SHOWN
    assert {d for d in disc if d in orig} == {d for d in orig if d in disc}


# Named attacks on the issuer JWT

def _swap_issuer_jwt(new_jwt: str) -> str:
    nonces = NonceStore()
    nonce, _, disc, _ = honest_parts(nonces)
    return "~".join([new_jwt, *disc, kb(new_jwt, disc, nonce)]), nonces


def _issuer_payload() -> dict:
    return json.loads(unb64(ISSUANCE.split("~")[0].split(".")[1]))


@pytest.mark.parametrize("alg", ["none", "None", "NONE", "", "HS256", "ES384", "ES256K", "es256", "RS256", "EdDSA"])
def test_issuer_algorithm_other_than_es256_is_refused(alg):
    token, nonces = _swap_issuer_jwt(jws({"alg": alg, "typ": "example+sd-jwt"}, _issuer_payload(), None))
    assert refused(token, nonces) == "wrong algorithm"


def test_alg_header_missing_is_refused():
    token, nonces = _swap_issuer_jwt(f"{b64j({'typ': 'JWT'})}.{b64j(_issuer_payload())}.")
    assert refused(token, nonces) == "wrong algorithm"


def test_hmac_with_the_kitchen_public_key_is_refused():
    """Key confusion: HS256 keyed with the kitchen's public key, under both alg names."""
    pub = KITCHEN.export_public()
    for alg in ("HS256", "ES256"):
        head, body = b64j({"alg": alg}), b64j(_issuer_payload())
        sig = b64(hmac.new(pub.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
        token, nonces = _swap_issuer_jwt(f"{head}.{body}.{sig}")
        assert refused(token, nonces) == ("wrong algorithm" if alg == "HS256" else "issuer signature does not verify")


@pytest.mark.parametrize("extra", [{"jwk": json.loads(MALLORY.export_public())}, {"kid": "kitchen-es256"},
                                   {"jku": "https://evil.example/jwks.json"}, {"x5u": "https://evil.example/c.pem"}])
def test_header_cannot_bring_its_own_key(extra):
    token, nonces = _swap_issuer_jwt(jws({"alg": "ES256", "typ": "example+sd-jwt", **extra}, _issuer_payload(),
                                         MALLORY))
    assert refused(token, nonces) == "issuer signature does not verify"


def test_pass_signed_by_the_agent_itself_is_refused():
    forged = issue_mandate({**DEMO_CLAIMS, "autoLimitCents": 10**9}, DEMO_SD_FIELDS, AGENT, AGENT)
    nonces = NonceStore()
    assert refused(present(forged, SHOWN, AGENT, AUDIENCE, nonces.issue(NOW), IAT), nonces) == \
        "issuer signature does not verify"


def test_kitchen_key_but_other_issuer_name_is_refused():
    other = issue_mandate({**DEMO_CLAIMS, "iss": "kitchen:elsewhere"}, DEMO_SD_FIELDS, KITCHEN, AGENT)
    nonces = NonceStore()
    assert refused(present(other, SHOWN, AGENT, AUDIENCE, nonces.issue(NOW), IAT), nonces) == "unknown issuer"


def test_pass_bound_to_another_holder_is_refused():
    """Mallory steals the issuance but holds another key: the cnf key in the signed payload is the agent's."""
    nonces = NonceStore()
    assert refused(present(ISSUANCE, SHOWN, MALLORY, AUDIENCE, nonces.issue(NOW), IAT), nonces) == \
        "holder key binding does not verify"


# Named attacks on the key-binding JWT

@pytest.mark.parametrize("variant", ["alg-none", "alg-hs256", "alg-es384", "foreign-key", "wrong-typ", "no-typ",
                                     "no-sd-hash", "no-aud", "wrong-aud", "aud-list", "nonce-int", "empty-kb"])
def test_key_binding_variants_are_refused(variant):
    nonces = NonceStore()
    nonce, jwt, disc, _ = honest_parts(nonces)
    if variant == "alg-none":
        kbjwt = kb(jwt, disc, nonce, alg="none", key=None)
    elif variant == "alg-hs256":
        head = b64j({"alg": "HS256", "typ": "kb+jwt"})
        body = b64j({"nonce": nonce, "aud": AUDIENCE, "iat": int(NOW.timestamp()), "sd_hash": sd_hash(jwt, disc)})
        sig = hmac.new(AGENT.export_public().encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
        kbjwt = f"{head}.{body}.{b64(sig)}"
    elif variant == "alg-es384":
        kbjwt = kb(jwt, disc, nonce, alg="ES384", key=JWK.generate(kty="EC", crv="P-384"))
    elif variant == "foreign-key":
        kbjwt = kb(jwt, disc, nonce, key=MALLORY)
    elif variant == "wrong-typ":
        kbjwt = kb(jwt, disc, nonce, typ="JWT")
    elif variant == "no-typ":
        kbjwt = jws({"alg": "ES256"}, {"nonce": nonce, "aud": AUDIENCE, "iat": 0, "sd_hash": sd_hash(jwt, disc)},
                    AGENT)
    elif variant == "no-sd-hash":
        kbjwt = kb(jwt, disc, nonce, drop=("sd_hash",))
    elif variant == "no-aud":
        kbjwt = kb(jwt, disc, nonce, drop=("aud",))
    elif variant == "wrong-aud":
        kbjwt = kb(jwt, disc, nonce, aud="validio:agent-v2")
    elif variant == "aud-list":
        kbjwt = jws({"alg": "ES256", "typ": "kb+jwt"}, {"nonce": nonce, "aud": [AUDIENCE], "iat": 0,
                                                        "sd_hash": sd_hash(jwt, disc)}, AGENT)
    elif variant == "nonce-int":
        kbjwt = jws({"alg": "ES256", "typ": "kb+jwt"}, {"nonce": 12345, "aud": AUDIENCE, "iat": 0,
                                                        "sd_hash": sd_hash(jwt, disc)}, AGENT)
    else:
        kbjwt = ""
    refused("~".join([jwt, *disc, kbjwt]), nonces)
    # the honest presentation with the same nonce still works: a refused one never burns it
    assert verify("~".join([jwt, *disc, kb(jwt, disc, nonce)]), nonces).id == "M-1"


@pytest.mark.parametrize("payload", [[1, 2], "nonce", 7, None])
def test_key_binding_payload_that_is_not_an_object_is_refused(payload):
    nonces = NonceStore()
    _nonce, jwt, disc, _ = honest_parts(nonces)
    bad = f"{b64j({'alg': 'ES256', 'typ': 'kb+jwt'})}.{b64j(payload)}.sig"
    refused("~".join([jwt, *disc, bad]), nonces)


@pytest.mark.parametrize("iat", [0, int((NOW + timedelta(days=365)).timestamp()),
                                 int((NOW - timedelta(days=30)).timestamp())])
def test_key_binding_iat_far_from_now_is_refused(iat):
    nonces = NonceStore()
    nonce, jwt, disc, _ = honest_parts(nonces)
    refused("~".join([jwt, *disc, kb(jwt, disc, nonce, iat=iat)]), nonces)


def test_unreferenced_disclosure_signed_by_the_holder_is_refused():
    nonces = NonceStore()
    nonce, jwt, disc, _ = honest_parts(nonces)
    forged = [*disc, b64j(["c2FsdHNhbHQ", "categories", ["104", "999"]])]
    refused("~".join([jwt, *forged, kb(jwt, forged, nonce)]), nonces)


def test_unreferenced_disclosure_never_changes_the_mandate():
    """Even while G4 stands, the forged field is not read: the limits are the kitchen's."""
    nonces = NonceStore()
    nonce, jwt, disc, _ = honest_parts(nonces)
    forged = [*disc, b64j(["c2FsdA", "autoLimitCents", 10**9]), b64j(["c2FsdA", "categories", ["999"]])]
    try:
        m = verify("~".join([jwt, *forged, kb(jwt, forged, nonce)]), nonces)
    except MandateError:
        return
    assert m.auto_limit_cents == 120000 and m.categories == ("104", "106", "418")


# Validity window and types inside a kitchen-signed pass

@pytest.mark.parametrize("change,reason", [
    ({"exp": int(NOW.timestamp())}, "Spend Pass expired"),
    ({"exp": int(NOW.timestamp()) - 1}, "Spend Pass expired"),
    ({"nbf": int(NOW.timestamp()) + 1}, "Spend Pass not valid yet"),
    ({"exp": float(DEMO_CLAIMS["exp"])}, "Spend Pass without validity window"),
    ({"exp": str(DEMO_CLAIMS["exp"])}, "Spend Pass without validity window"),
    ({"nbf": None}, "Spend Pass without validity window"),
    ({"autoLimitCents": 1200.5}, "money must be whole cents"),
    ({"autoLimitCents": "120000"}, "money must be whole cents"),
    ({"hardCapCents": True}, "money must be whole cents"),
])
def test_kitchen_signed_odd_values_are_refused(change, reason):
    claims = {k: v for k, v in {**DEMO_CLAIMS, **change}.items() if v is not None}
    nonces = NonceStore()
    token = present(issue_mandate(claims, DEMO_SD_FIELDS, KITCHEN, AGENT), SHOWN, AGENT, AUDIENCE, nonces.issue(NOW), IAT)
    assert refused(token, nonces) == reason


def test_pass_issued_in_the_future_is_refused():
    claims = {**DEMO_CLAIMS, "iat": int((NOW + timedelta(days=2)).timestamp())}
    nonces = NonceStore()
    token = present(issue_mandate(claims, DEMO_SD_FIELDS, KITCHEN, AGENT), SHOWN, AGENT, AUDIENCE, nonces.issue(NOW), IAT)
    refused(token, nonces)


# Nonces

def test_concurrent_replay_wins_once():
    nonces = NonceStore()
    token = present(ISSUANCE, SHOWN, AGENT, AUDIENCE, nonces.issue(NOW), IAT)
    barrier, results = threading.Barrier(8), []

    def go():
        barrier.wait()
        try:
            verify(token, nonces)
            results.append("ok")
        except MandateError as e:
            results.append(str(e))

    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 1, results
    assert set(results) - {"ok"} == {"unknown or reused nonce"}


def test_nonce_from_another_store_is_refused():
    other = NonceStore()
    token = present(ISSUANCE, SHOWN, AGENT, AUDIENCE, other.issue(NOW), IAT)
    assert refused(token, NonceStore()) == "unknown or reused nonce"


def test_nonce_exactly_at_and_after_ttl():
    nonces = NonceStore(ttl=timedelta(minutes=5))
    token = present(ISSUANCE, SHOWN, AGENT, AUDIENCE, nonces.issue(NOW), IAT)
    assert refused(token, nonces, now=NOW + timedelta(minutes=5, seconds=1)) == "stale nonce"
    assert verify(token, nonces, now=NOW + timedelta(minutes=5)).id == "M-1"


# Over the wire: /agent/v1 and MCP give the same refusals

MILK = [{"text": "10 litres of lactose-free milk by Monday"}]


@pytest.fixture
def wire(ctx):
    """Tokens for the runtime's real kitchen and agent keys, nonces from its store."""
    from validio.agent.holder import Holder
    from validio.api import tools

    h = Holder.from_seed(lambda: tools.nonce(ctx), ctx.db_path, ctx.keys_dir)
    return ctx, h


def _bad_tokens(ctx, h):
    from validio.api import tools

    good = h.presentation()
    jwt, *disc, _ = good.split("~")
    nonce = tools.nonce(ctx).nonce
    none_jwt = f"{b64j({'alg': 'none'})}.{jwt.split('.')[1]}."
    payload = json.loads(unb64(jwt.split(".")[1]))
    forged = jws({"alg": "ES256", "typ": "example+sd-jwt"}, payload, MALLORY)
    return {
        "alg none": ("~".join([none_jwt, *disc, kb(none_jwt, disc, nonce, key=h.key)]), "wrong algorithm"),
        "foreign issuer key": ("~".join([forged, *disc, kb(forged, disc, nonce, key=h.key)]),
                               "issuer signature does not verify"),
        "foreign holder key": (present(h.issuance, SHOWN, MALLORY, AUDIENCE, tools.nonce(ctx).nonce, IAT),
                               "holder key binding does not verify"),
        "no key binding": (h.issuance, "no key binding"),
        "made-up nonce": (present(h.issuance, SHOWN, h.key, AUDIENCE, "made-up", IAT), "unknown or reused nonce"),
    }


def test_http_refuses_each_with_its_reason(wire):
    from fastapi.testclient import TestClient

    from validio.api.app import app

    ctx, h = wire
    with TestClient(app) as client:
        for name, (token, reason) in _bad_tokens(ctx, h).items():
            r = client.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {token}"},
                            json={"lines": MILK, "idempotencyKey": f"bad-{name}"})
            assert r.status_code == 401, (name, r.text)
            assert r.json()["detail"] == reason, name
            assert r.headers.get("www-authenticate") == "SD-JWT"
        for header in ("", "SD-JWT", "SD-JWT    ", "Basic dXNlcjpwYXNz", "Bearer", "JWT x.y.z"):
            r = client.post("/agent/v1/requests", headers={"Authorization": header} if header else {},
                            json={"lines": MILK, "idempotencyKey": "hdr"})
            assert r.status_code == 401, header
        assert ctx.valio.calls == 0, "a refused pass must not reach Valio"


@pytest.mark.asyncio
async def test_mcp_refuses_each_with_its_reason(wire):
    from mcp import Client

    from validio.api.mcp_server import server

    ctx, h = wire
    async with Client(server) as c:
        for name, (token, reason) in _bad_tokens(ctx, h).items():
            r = await c.call_tool("request_supply", {"spendPass": token, "lines": MILK, "idempotencyKey": name})
            text = " ".join(getattr(x, "text", "") for x in r.content)
            assert r.is_error and text.endswith(f"401 Spend Pass refused: {reason}"), (name, text)
    assert ctx.valio.calls == 0


@pytest.mark.asyncio
async def test_replay_across_http_and_mcp_and_tools(wire):
    """One presentation, used once over HTTP, is dead for MCP, for confirm_order and for HTTP again."""
    from fastapi.testclient import TestClient
    from mcp import Client

    from validio.api.app import app
    from validio.api.mcp_server import server

    ctx, h = wire
    token = h.presentation()
    with TestClient(app) as client:
        r = client.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {token}"},
                        json={"lines": MILK, "idempotencyKey": "first"})
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        again = client.post("/agent/v1/orders", headers={"Authorization": f"Bearer {token}"},
                            json={"requestId": rid, "idempotencyKey": "o", "choice": [{"productId": "464306",
                                                                                         "salesQty": 10}]})
        assert again.status_code == 401 and again.json()["detail"] == "unknown or reused nonce"
    async with Client(server) as c:
        for tool, args in (("request_supply", {"lines": MILK, "idempotencyKey": "first"}),
                           ("confirm_order", {"requestId": rid, "choice": [{"productId": "464306", "salesQty": 10}],
                                              "idempotencyKey": "o"})):
            r = await c.call_tool(tool, {**args, "spendPass": token})
            text = " ".join(getattr(x, "text", "") for x in r.content)
            assert r.is_error and text.endswith("unknown or reused nonce"), (tool, text)
    assert ctx.orders.store.order("O-1") is None, "nothing was ordered with the replayed pass"


def test_reset_kills_every_outstanding_nonce(wire):
    from conftest import TOKEN
    from fastapi.testclient import TestClient

    from validio.api.app import app

    _ctx, h = wire
    token = h.presentation()  # nonce issued before the reset
    with TestClient(app) as client:
        assert client.post("/api/demo/reset", headers={"X-Demo-Token": TOKEN}).status_code == 200
        r = client.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {token}"},
                        json={"lines": MILK, "idempotencyKey": "after-reset"})
    assert r.status_code == 401 and r.json()["detail"] == "unknown or reused nonce"


def test_http_key_binding_payload_that_is_not_an_object_is_401(wire):
    from fastapi.testclient import TestClient

    from validio.api.app import app

    _ctx, h = wire
    jwt, *disc, _ = h.presentation().split("~")
    bad = "~".join([jwt, *disc, f"{b64j({'alg': 'ES256', 'typ': 'kb+jwt'})}.{b64j([1])}.sig"])
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {bad}"},
                        json={"lines": MILK, "idempotencyKey": "kb-list"})
    assert r.status_code == 401, r.status_code
