"""A third-party purchasing agent for Validio in one file: scene 2 over /agent/v1.

It needs httpx for HTTP and jwcrypto for the one ES256 signature of the key binding. It holds two
things the kitchen gave it: the issued Spend Pass (an SD-JWT) and its own P-256 key as a JWK.

    uv run python examples/agent_client.py --pass pass.txt --key data/keys/agent-es256.json
"""

import argparse
import base64
import hashlib
import json
import time

import httpx
from jwcrypto import jwk, jws

AUD = "validio:agent-v1"
DISCLOSE = {"autoLimitCents", "hardCapCents", "diet"}  # all a decision needs, nothing more


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def presentation(issuance: str, key_json: str, nonce: str) -> str:
    """Issuer JWT, the disclosures we choose to show, then a KB-JWT signed with our key over the nonce."""
    jwt, *disclosures = [p for p in issuance.split("~") if p]
    shown = [d for d in disclosures if json.loads(b64d(d))[1] in DISCLOSE]
    sd = "~".join([jwt, *shown]) + "~"
    claims = {"iat": int(time.time()), "aud": AUD, "nonce": nonce,
              "sd_hash": b64e(hashlib.sha256(sd.encode()).digest())}
    kb = jws.JWS(json.dumps(claims))
    kb.add_signature(jwk.JWK.from_json(key_json), alg="ES256", protected={"alg": "ES256", "typ": "kb+jwt"})
    return sd + kb.serialize(compact=True)


def ok(r: httpx.Response) -> dict:
    if r.is_error:  # every Validio error is {"detail": ...}
        raise SystemExit(f"{r.status_code} {r.json()['detail']}")
    return r.json()


def scene2(http: httpx.Client, issuance: str, key_json: str) -> dict:
    def auth() -> dict:  # a fresh nonce for every write, each one is good once
        nonce = ok(http.get("/agent/v1/nonce"))["nonce"]
        return {"Authorization": f"SD-JWT {presentation(issuance, key_json, nonce)}"}

    req = ok(http.post("/agent/v1/requests", headers=auth(), json={
        "lines": [{"text": "1000 litres of lactose-free milk by Monday, budget 1200 euro"}],
        "deliverBy": "2026-11-16", "idempotencyKey": "example-scene2-request"}))
    decision = req["decision"]
    print(f"request {req['id']}: {decision['outcome']}, {decision['sentence']}")
    if decision["outcome"] == "ask_human":  # Validio already holds the order for the owner
        return ok(http.get(f"/agent/v1/orders/{req['orderId']}"))
    if decision["outcome"] != "auto_order":
        raise SystemExit("blocked, nothing ordered")
    choice = [{"productId": ln["chosen"]["productId"], "salesQty": ln["chosen"]["salesQty"]}
              for ln in req["lines"] if ln.get("chosen")]
    order = ok(http.post("/agent/v1/orders", headers=auth(), json={
        "requestId": req["id"], "choice": choice, "idempotencyKey": "example-scene2-order"}))
    order = ok(http.get(f"/agent/v1/orders/{order['id']}"))
    print(f"order {order['id']}: {order['state']}, {order['totalCents'] / 100:.2f} EUR")
    return order


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8410")
    ap.add_argument("--pass", dest="pass_file", required=True, help="the issued Spend Pass, one line")
    ap.add_argument("--key", required=True, help="the agent's private P-256 key as a JWK")
    a = ap.parse_args()
    with open(a.pass_file) as p, open(a.key) as k, httpx.Client(base_url=a.base, timeout=30) as http:
        scene2(http, p.read().strip(), k.read())
