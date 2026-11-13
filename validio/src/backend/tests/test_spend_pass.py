"""Step 6, Spend Pass: SD-JWT with key binding, ES256, single-use nonce, expiry checked by us."""

from datetime import datetime, timedelta

import pytest
from jwcrypto.jwk import JWK

from validio.policy.mandate import (
    AUDIENCE,
    DEMO_CLAIMS,
    DEMO_SD_FIELDS,
    MandateError,
    NonceStore,
    issue_mandate,
    load_or_create_key,
    present,
    verify_presentation,
)

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
SHOWN = {"autoLimitCents", "hardCapCents", "diet"}


@pytest.fixture(scope="module")
def keys():
    return JWK.generate(kty="EC", crv="P-256"), JWK.generate(kty="EC", crv="P-256")


@pytest.fixture(scope="module")
def issuance(keys):
    kitchen, agent = keys
    return issue_mandate(DEMO_CLAIMS, DEMO_SD_FIELDS, kitchen, agent)


def _verify(token, keys, nonces, now=NOW):
    kitchen, _ = keys
    return verify_presentation(
        token, kitchen_pub=kitchen, issuer="kitchen:hotel-espoo", aud=AUDIENCE, nonces=nonces, now=now
    )


def _present(issuance, keys, nonces, disclose=SHOWN, now=NOW, agent=None):
    nonce = nonces.issue(now)
    return present(issuance, disclose, agent or keys[1], AUDIENCE, nonce, int(now.timestamp()))


def test_demo_pass_matches_blueprint():
    assert DEMO_CLAIMS["iss"] == "kitchen:hotel-espoo"
    assert DEMO_CLAIMS["sub"] == "agent:buyer-1"
    assert DEMO_CLAIMS["jti"] == "M-1"
    assert datetime.fromtimestamp(DEMO_CLAIMS["nbf"]).astimezone(NOW.tzinfo) == NOW
    # valid until 17 Nov 00:00
    assert DEMO_CLAIMS["exp"] - DEMO_CLAIMS["nbf"] == int(timedelta(hours=62).total_seconds())
    assert DEMO_CLAIMS["autoLimitCents"] == 120000
    assert DEMO_CLAIMS["hardCapCents"] == 200000
    assert DEMO_CLAIMS["diet"] == ["FREE_FROM_LACTOSE"]
    assert DEMO_SD_FIELDS == {"autoLimitCents", "hardCapCents", "diet", "preferLabels", "approvers"}


def test_issued_pass_is_es256(issuance):
    import base64
    import json

    header = issuance.split("~")[0].split(".")[0]
    assert json.loads(base64.urlsafe_b64decode(header + "=="))["alg"] == "ES256"


def test_hidden_fields_are_not_in_the_signed_payload(issuance):
    import base64

    payload = issuance.split("~")[0].split(".")[1]
    raw = base64.urlsafe_b64decode(payload + "==")
    for word in (b"120000", b"200000", b"owner:anna", b"approvers", b"FREE_FROM_LACTOSE"):
        assert word not in raw


def test_presented_pass_shows_only_disclosed(issuance, keys):
    nonces = NonceStore()
    m = _verify(_present(issuance, keys, nonces), keys, nonces)
    assert m.id == "M-1"
    assert m.issuer == "kitchen:hotel-espoo"
    assert m.holder == "agent:buyer-1"
    assert m.auto_limit_cents == 120000
    assert m.hard_cap_cents == 200000
    assert m.diet == ("FREE_FROM_LACTOSE",)
    assert m.categories == ("104", "106", "418")
    assert m.deliver_by == "2026-11-16"
    assert m.split_max_extra_bp == 500
    assert m.disclosed == {"autoLimitCents": 120000, "hardCapCents": 200000, "diet": ["FREE_FROM_LACTOSE"]}
    assert "approvers" not in m.disclosed


def test_undisclosed_budget_is_none(issuance, keys):
    nonces = NonceStore()
    m = _verify(_present(issuance, keys, nonces, disclose={"diet"}), keys, nonces)
    assert m.auto_limit_cents is None
    assert m.hard_cap_cents is None
    assert m.disclosed == {"diet": ["FREE_FROM_LACTOSE"]}


def test_expired_mandate_rejected(issuance, keys):
    # sd-jwt does not check exp, this proves we do
    nonces = NonceStore()
    late = datetime.fromisoformat("2026-11-17T00:00:01+02:00")
    token = _present(issuance, keys, nonces, now=late)
    with pytest.raises(MandateError, match="expired"):
        _verify(token, keys, nonces, now=late)


def test_not_yet_valid_rejected(issuance, keys):
    nonces = NonceStore()
    early = NOW - timedelta(seconds=1)
    token = _present(issuance, keys, nonces, now=early)
    with pytest.raises(MandateError, match="not valid yet"):
        _verify(token, keys, nonces, now=early)


def test_wrong_nonce_rejected(issuance, keys):
    nonces = NonceStore()
    nonces.issue(NOW)
    token = present(issuance, SHOWN, keys[1], AUDIENCE, "made-up-nonce", iat=int(NOW.timestamp()))
    with pytest.raises(MandateError, match="nonce"):
        _verify(token, keys, nonces)


def test_reused_nonce_rejected(issuance, keys):
    nonces = NonceStore()
    token = _present(issuance, keys, nonces)
    _verify(token, keys, nonces)
    with pytest.raises(MandateError, match="nonce"):
        _verify(token, keys, nonces)


def test_stale_nonce_rejected(issuance, keys):
    nonces = NonceStore(ttl=timedelta(minutes=5))
    token = _present(issuance, keys, nonces)
    with pytest.raises(MandateError, match="nonce"):
        _verify(token, keys, nonces, now=NOW + timedelta(minutes=6))


def test_foreign_holder_key_rejected(issuance, keys):
    nonces = NonceStore()
    token = _present(issuance, keys, nonces, agent=JWK.generate(kty="EC", crv="P-256"))
    with pytest.raises(MandateError, match="^holder key binding does not verify$"):
        _verify(token, keys, nonces)


def test_foreign_issuer_key_rejected(keys):
    nonces = NonceStore()
    forged = issue_mandate(DEMO_CLAIMS, DEMO_SD_FIELDS, JWK.generate(kty="EC", crv="P-256"), keys[1])
    token = _present(forged, keys, nonces)
    with pytest.raises(MandateError, match="^issuer signature does not verify$"):
        _verify(token, keys, nonces)


def test_wrong_audience_rejected(issuance, keys):
    nonces = NonceStore()
    token = present(issuance, SHOWN, keys[1], "https://elsewhere.example", nonces.issue(NOW), iat=int(NOW.timestamp()))
    with pytest.raises(MandateError, match="^wrong audience$"):
        _verify(token, keys, nonces)


def test_tampered_token_rejected(issuance, keys):
    import base64
    import json

    nonces = NonceStore()
    token = _present(issuance, keys, nonces)
    jwt, *rest = token.split("~")
    h, p, s = jwt.split(".")
    body = json.loads(base64.urlsafe_b64decode(p + "=="))
    body["deliverBy"] = "2026-12-24"
    p2 = base64.urlsafe_b64encode(json.dumps(body).encode()).rstrip(b"=").decode()
    with pytest.raises(MandateError, match="^issuer signature does not verify$"):
        _verify("~".join([f"{h}.{p2}.{s}", *rest]), keys, nonces)


def test_garbage_rejected(keys):
    with pytest.raises(MandateError, match="^no key binding$"):
        _verify("not-a-token", keys, NonceStore())


def test_presentation_without_key_binding_rejected(issuance, keys):
    nonces = NonceStore()
    nonces.issue(NOW)
    with pytest.raises(MandateError, match="^no key binding$"):
        _verify(issuance, keys, nonces)  # the bare issuance has no KB-JWT


def _b64(x) -> str:
    import base64
    import json

    return base64.urlsafe_b64encode(json.dumps(x).encode()).rstrip(b"=").decode()


def test_added_disclosure_rejected(issuance, keys):
    nonces = NonceStore()
    parts = _present(issuance, keys, nonces).split("~")
    token = "~".join([*parts[:-1], _b64(["salt", "approvers", ["owner:mallory"]]), parts[-1]])
    with pytest.raises(MandateError, match="^disclosures do not match the key binding$"):
        _verify(token, keys, nonces)


def test_removed_disclosure_rejected(issuance, keys):
    nonces = NonceStore()
    parts = _present(issuance, keys, nonces).split("~")
    with pytest.raises(MandateError, match="^disclosures do not match the key binding$"):
        _verify("~".join([parts[0], *parts[2:]]), keys, nonces)


def test_failed_check_keeps_the_nonce_unused(issuance, keys):
    # a rejected presentation must not burn the nonce of a later honest one
    nonces = NonceStore()
    nonce = nonces.issue(NOW)
    bad = present(issuance, SHOWN, keys[1], "https://elsewhere.example", nonce, iat=int(NOW.timestamp()))
    with pytest.raises(MandateError, match="^wrong audience$"):
        _verify(bad, keys, nonces)
    assert _verify(present(issuance, SHOWN, keys[1], AUDIENCE, nonce, iat=int(NOW.timestamp())), keys, nonces).id == "M-1"


def test_key_file_round_trip(tmp_path):
    path = tmp_path / "keys" / "kitchen.jwk"
    k1 = load_or_create_key(path)
    k2 = load_or_create_key(path)
    assert k1.thumbprint() == k2.thumbprint()
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_nonce_store_is_capped():
    nonces = NonceStore(max_open=3)
    for _ in range(3):
        nonces.issue(NOW)
    with pytest.raises(MandateError, match="^too many open nonces$"):
        nonces.issue(NOW)
    # expired nonces make room again
    assert nonces.issue(NOW + timedelta(minutes=6))
