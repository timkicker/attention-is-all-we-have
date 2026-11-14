"""B4: connect an agent to the kitchen. Pairing code, the agent's key, consent, Allow signs the pass to that
key; Pause refuses at verify with a ledger entry; Disconnect bumps the version and never revokes."""

import re
from datetime import datetime

from asking import pair_demo_agent
from jwcrypto.jwk import JWK
from test_api import auth, client, holder  # noqa: F401

from validio.agent.holder import Holder

MILK = "500 litres of lactose-free milk by Monday"


def ask(client, h, key, text=MILK):  # noqa: F811
    return client.post("/agent/v1/requests", headers=auth(h),
                       json={"lines": [{"text": text}], "deliverBy": "2026-11-16", "idempotencyKey": key})


def agent_entries(client):  # noqa: F811
    return [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "agent"]


def pair_own_agent(client, name="Kitchen buyer"):  # noqa: F811
    """A third-party agent with its own key, paired through the code the web app shows."""
    key = JWK.generate(kty="EC", crv="P-256")
    state = client.post("/api/agent/pair").json()
    code = state["pairing"]["code"]
    r = client.post("/agent/v1/pair", json={"code": code, "name": name, "publicJwk": key.export_public(as_dict=True)})
    assert r.status_code == 202, r.text
    return key, code


def test_a_signing_agent_gets_the_verification_code_of_the_consent_screen(client):  # noqa: F811
    client.post("/api/agent/disconnect")
    codes = []
    for _ in range(2):
        key = JWK.generate(kty="EC", crv="P-256")
        code = client.post("/api/agent/pair").json()["pairing"]["code"]
        r = client.post("/agent/v1/pair", json={"code": code, "name": "Kitchen buyer",
                                                "publicJwk": key.export_public(as_dict=True)})
        assert r.status_code == 202 and re.fullmatch(r"[A-HJKMNP-Z2-9]{3}-[A-HJKMNP-Z2-9]{3}", r.json()["verifyCode"])
        consent = client.get("/api/agent").json()["consent"]
        assert consent["verifyCode"] == r.json()["verifyCode"]
        assert datetime.fromisoformat(consent["at"]).tzinfo is not None  # when the agent's first call came
        codes.append(r.json()["verifyCode"])
        client.post("/api/agent/deny")
        assert "consent" not in client.get("/api/agent").json()
    assert codes[0] != codes[1]


def test_a_seeded_kitchen_has_the_demo_agent(client):  # noqa: F811
    s = client.get("/api/agent").json()
    assert s["state"] == "active"
    assert s["agent"]["name"] == "Demo agent" and s["agent"]["passId"] == "M-1"
    assert s["agent"]["passVersion"] == 1 and len(s["agent"]["keyId"]) == 8
    assert [v["version"] for v in s["versions"]] == [1]


def test_disconnect_bumps_the_version_and_refuses_the_old_copy(client, holder, ctx):  # noqa: F811
    s = client.post("/api/agent/disconnect").json()
    assert s["state"] == "none" and "agent" not in s
    assert [v["version"] for v in s["versions"]] == [2, 1]
    assert s["versions"][0]["why"] == "Agent disconnected"
    r = ask(client, holder, "after")
    assert r.status_code == 401 and "superseded" in r.json()["detail"]
    assert not ctx.store.is_revoked("M-1")  # never revoked, so a new agent can get M-1 back
    assert [e["sentence"] for e in agent_entries(client)] == [
        "Disconnected Demo agent. Spend Pass M-1 is now version 2, the agent's copy is refused."]
    assert client.get("/api/spend-passes/M-1").status_code == 200  # the page still shows the pass


def test_pairing_shows_a_code_and_the_urls(client):  # noqa: F811
    assert client.post("/api/agent/pair").status_code == 409  # an agent is connected
    client.post("/api/agent/disconnect")
    s = client.post("/api/agent/pair").json()
    assert s["state"] == "pairing"
    assert re.fullmatch(r"[2-9A-HJKMNP-Z]{4}-[2-9A-HJKMNP-Z]{4}", s["pairing"]["code"])
    assert re.search(r"/mcp/c/[A-Za-z0-9_-]{43}/$", s["pairing"]["mcpUrl"]) and s["pairing"]["apiUrl"].endswith("/agent/v1")
    again = client.post("/api/agent/pair").json()
    assert again["pairing"]["code"] != s["pairing"]["code"]  # a new code each time


def test_wrong_code_and_private_key_are_refused(client):  # noqa: F811
    client.post("/api/agent/disconnect")
    code = client.post("/api/agent/pair").json()["pairing"]["code"]
    key = JWK.generate(kty="EC", crv="P-256")
    r = client.post("/agent/v1/pair", json={"code": "AAAA-AAAA", "name": "x", "publicJwk": key.export_public(as_dict=True)})
    assert r.status_code == 404
    r = client.post("/agent/v1/pair", json={"code": code, "name": "x", "publicJwk": key.export_private(as_dict=True)})
    assert r.status_code == 422
    assert client.get("/api/agent").json()["state"] == "pairing"


def test_five_wrong_codes_end_the_pairing(client):  # noqa: F811
    client.post("/api/agent/disconnect")
    code = client.post("/api/agent/pair").json()["pairing"]["code"]
    pub = JWK.generate(kty="EC", crv="P-256").export_public(as_dict=True)
    for _ in range(5):
        client.post("/agent/v1/pair", json={"code": "AAAA-AAAA", "name": "x", "publicJwk": pub})
    assert client.post("/agent/v1/pair", json={"code": code, "name": "x", "publicJwk": pub}).status_code == 404
    assert client.get("/api/agent").json()["state"] == "none"


def test_consent_then_allow_signs_the_pass_to_the_agents_key(client, holder, ctx):  # noqa: F811
    client.post("/api/agent/disconnect")
    key, code = pair_own_agent(client)
    s = client.get("/api/agent").json()
    assert s["state"] == "consent"
    assert s["consent"]["name"] == "Kitchen buyer"
    assert s["consent"]["keyId"] == key.thumbprint()[:8]
    assert s["consent"]["may"] == ["Orders alone up to 1,200.00 €", "Needs approval up to 2,000.00 €",
                                   "Blocked above 2,000.00 €", "Substitutes up to 5 % extra"]
    assert client.get("/api/rules").json()["maxExtraPct"] == 5  # the consent says what Rules say
    assert client.get("/agent/v1/pass", params={"code": code}).json() == {"status": "consent"}

    s = client.post("/api/agent/allow").json()
    assert s["state"] == "active" and s["agent"]["name"] == "Kitchen buyer" and s["agent"]["passVersion"] == 3
    assert s["versions"][0] == {**s["versions"][0], "version": 3, "why": "Agent connected"}
    got = client.get("/agent/v1/pass", params={"code": code.replace("-", "")}).json()
    assert got["status"] == "allowed"
    mine = Holder(got["spendPass"], key, lambda: client.get("/agent/v1/nonce").json())
    r = ask(client, mine, "own")
    assert r.status_code == 200, r.text
    assert r.json()["decision"]["outcome"] == "auto_order"
    assert ask(client, holder, "demo").status_code == 401  # the demo key no longer holds the pass
    assert client.get("/api/agent").json()["agent"]["lastUsedAt"] is not None
    assert client.get("/api/spend-passes/M-1").json()["autoLimitCents"] == 120000
    assert agent_entries(client)[-1]["sentence"] == (
        "Connected Kitchen buyer. Spend Pass M-1 is now version 3, signed to its key.")
    assert client.post("/api/agent/allow").status_code == 409  # nothing left to allow


def test_deny_tells_the_agent(client):  # noqa: F811
    client.post("/api/agent/disconnect")
    _, code = pair_own_agent(client)
    assert client.post("/api/agent/deny").json()["state"] == "none"
    assert client.get("/agent/v1/pass", params={"code": code}).json() == {"status": "denied"}
    assert client.get("/agent/v1/pass", params={"code": "ZZZZ-ZZZZ"}).status_code == 404


def test_pause_refuses_at_verify_and_writes_one_entry_each_time(client, holder):  # noqa: F811
    s = client.post("/api/agent/pause", json={"paused": True}).json()
    assert s["state"] == "paused"
    r = ask(client, holder, "p1")
    assert r.status_code == 401 and r.json()["detail"] == "the kitchen paused this agent"
    sentences = [e["sentence"] for e in agent_entries(client)]
    assert sentences == ["Paused Demo agent.", "Refused Demo agent: the kitchen paused this agent."]
    assert all(e["spendPassId"] == "M-1" for e in agent_entries(client))
    assert client.get("/api/spend-passes/M-1").status_code == 200  # looking at the pass is not agent use
    assert len(agent_entries(client)) == 2

    s = client.post("/api/agent/pause", json={"paused": False}).json()
    assert s["state"] == "active" and s["agent"]["passVersion"] == 1  # the same pass comes back
    assert ask(client, holder, "p2").status_code == 200
    assert agent_entries(client)[-1]["sentence"] == "Resumed Demo agent."


def test_pause_needs_an_agent(client):  # noqa: F811
    client.post("/api/agent/disconnect")
    assert client.post("/api/agent/pause", json={"paused": True}).status_code == 409


def test_demo_agent_answers_the_code_and_gets_the_pass_back(client, ctx):  # noqa: F811
    client.post("/api/agent/disconnect")
    pair_demo_agent(ctx)  # the demo agent's key answers the code like any signing agent
    s = client.get("/api/agent").json()
    assert s["state"] == "consent" and s["consent"]["name"] == "Demo agent"
    s = client.post("/api/agent/allow").json()
    assert s["state"] == "active" and s["agent"]["passVersion"] == 3
    h = Holder.from_seed(lambda: client.get("/agent/v1/nonce").json(), ctx.db_path, ctx.keys_dir)
    assert ask(client, h, "demo-back").status_code == 200


def test_rules_resign_keeps_the_connected_agent(client, ctx):  # noqa: F811
    from conftest import CODE

    client.post("/api/agent/disconnect")
    key, _ = pair_own_agent(client)
    client.post("/api/agent/allow")
    r = client.post("/api/spend-pass", headers={"X-Approve-Code": CODE}, json={
        "autoLimitCents": 160000, "hardCapCents": 250000, "diet": ["FREE_FROM_LACTOSE"],
        "deliverBy": "2026-11-16", "substitutes": True})
    assert r.status_code == 200, r.text
    from validio.demo import seed

    issuance = seed.issuance(ctx.db_path)
    mine = Holder(issuance, key, lambda: client.get("/agent/v1/nonce").json())
    assert ask(client, mine, "after-rules").status_code == 200
    s = client.get("/api/agent").json()
    assert s["agent"]["passVersion"] == 4 and s["versions"][0]["why"] == "Rules changed"


def test_consent_says_the_rules_as_saved(client):  # noqa: F811
    from conftest import CODE

    client.post("/api/agent/disconnect")
    r = client.put("/api/rules", headers={"X-Approve-Code": CODE}, json={
        "aloneUpToCents": 100000, "approvalUpToCents": 300000, "perWeekCents": 800000,
        "substitutes": "extra", "maxExtraPct": 5})
    assert r.status_code == 200, r.text
    pair_own_agent(client)
    assert client.get("/api/agent").json()["consent"]["may"] == [
        "Orders alone up to 1,000.00 €", "Needs approval up to 3,000.00 €", "Blocked above 3,000.00 €",
        "Per week up to 8,000.00 €", "Substitutes up to 5 % extra"]


def test_a_kitchen_left_unconnected_refuses_every_pass_until_allowed(client, holder, ctx):  # noqa: F811
    from validio.api import connect

    before = len(client.get("/api/ledger").json()["entries"])
    connect.leave_unconnected(ctx.db_path)
    s = client.get("/api/agent").json()
    assert s["state"] == "none" and [v["version"] for v in s["versions"]] == [1]
    assert len(client.get("/api/ledger").json()["entries"]) == before  # quiet
    r = ask(client, holder, "unconnected")
    assert r.status_code == 401 and r.json()["detail"] == "no agent is connected to this kitchen"
    pair_demo_agent(ctx)
    assert client.post("/api/agent/allow").json()["agent"]["passVersion"] == 2
    h = Holder.from_seed(lambda: client.get("/agent/v1/nonce").json(), ctx.db_path, ctx.keys_dir)
    assert ask(client, h, "connected").status_code == 200


def test_settings_resign_names_the_version(client):  # noqa: F811
    from conftest import CODE

    r = client.put("/api/settings/diet", json={"diet": ["FREE_FROM_LACTOSE", "FREE_FROM_GLUTEN"], "code": CODE})
    assert r.status_code == 200, r.text
    assert client.get("/api/agent").json()["versions"][0]["why"] == "Diet changed"
