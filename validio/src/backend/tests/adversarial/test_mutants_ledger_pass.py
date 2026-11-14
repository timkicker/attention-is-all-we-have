"""Tests written to kill mutants that survived mutmut in audit/log.py and policy/mandate.py (docs/TESTING.md).

Each test names the behaviour it pins; the mutant it was written for is in the comment."""

import base64
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timedelta

import pytest
from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS

from validio.audit.log import GENESIS, HEAD_TYP, AuditLog, VerifyResult, _entry, entry_hash
from validio.policy.mandate import (
    DEMO_CLAIMS,
    DEMO_SD_FIELDS,
    MandateError,
    NonceStore,
    _b64,
    _check_disclosures,
    _digests,
    _kb_payload,
    _mandate,
    issue_mandate,
    load_or_create_key,
    present,
    verify_presentation,
)

from .test_spend_pass_fuzz import AGENT, AUDIENCE, ISSUER, KITCHEN, NOW, b64, honest_parts, jws, kb

AT = datetime.fromisoformat("2026-11-14T10:00:00+02:00")


def _append(log: AuditLog, n: int = 1, facts=None):
    for i in range(n):
        log.append(at=AT, actor="buyer-1", kind="decision", sentence=f"entry {i}", facts=facts or [],
                   mandate_id="M-1", disclosed={}, rule_ids=[], order_id=f"O-{i}")


def _ledger(tmp_path, n=3):
    log = AuditLog(tmp_path / "ledger.db")
    _append(log, n)
    return log


# audit/log.py

def test_ledger_in_a_new_nested_folder(tmp_path):
    # mkdir(parents=False)
    log = AuditLog(tmp_path / "a" / "b" / "ledger.db")
    _append(log)
    assert log.verify() == VerifyResult(True, 1, None)


def test_failed_append_rolls_back_and_the_next_append_works(tmp_path):
    # ROLLBACK -> None / "XXROLLBACKXX": the connection stays inside the transaction
    log = _ledger(tmp_path, 2)
    with pytest.raises(TypeError):
        _append(log, facts=[{"x": object()}])  # not JSON
    _append(log)
    assert log.verify() == VerifyResult(True, 3, None)
    assert [e.seq for e in log.list()] == [1, 2, 3]


def test_failed_open_rolls_back(tmp_path):
    # ROLLBACK in __init__: an old ledger table without a hash column fails on the anchor query
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE ledger (seq INTEGER PRIMARY KEY, order_id TEXT, body TEXT NOT NULL)")
    con.commit()
    con.close()
    with pytest.raises(sqlite3.OperationalError, match="hash"):
        AuditLog(path)
    con = sqlite3.connect(path)
    assert con.execute("SELECT name FROM sqlite_master WHERE name = 'ledger_head'").fetchone() is None


def _rows(log):
    return log._con.execute("SELECT seq, body, hash FROM ledger ORDER BY seq").fetchall()


def test_unreadable_body_gives_exact_result(tmp_path):
    # VerifyResult(None, ...) or a count of None: /api/ledger shows ok and count as they are
    log = _ledger(tmp_path)
    log._con.execute("UPDATE ledger SET body = 'not json' WHERE seq = 2")
    r = log.verify()
    assert r == VerifyResult(False, 1, 2)
    assert r.ok is False and r.count == 1


def test_missing_head_gives_exact_result(tmp_path):
    log = _ledger(tmp_path)
    log._con.execute("DELETE FROM ledger_head")
    r = log.verify()
    assert r.ok is False and r.count == 3 and r.broken_at == 1


def test_body_seq_rewritten_with_hash_and_head(tmp_path):
    # `stored_seq != expected or body seq != stored` -> `and`: the body says seq 99 in row 3
    log = _ledger(tmp_path)
    seq, body, _ = _rows(log)[-1]
    body = {**json.loads(body), "seq": 99}
    h = entry_hash(body)
    log._con.execute("UPDATE ledger SET body = ?, hash = ? WHERE seq = ?", (json.dumps(body), h, seq))
    log._con.execute("UPDATE ledger_head SET hash = ? WHERE id = 1", (h,))
    assert log.verify() == VerifyResult(False, 2, 3)


def test_head_count_zeroed(tmp_path):
    # max(head count, 1) -> max(head count, 2)
    log = _ledger(tmp_path)
    log._con.execute("UPDATE ledger_head SET count = 0 WHERE id = 1")
    assert log.verify() == VerifyResult(False, 3, 1)


def test_empty_ledger_head_is_genesis(tmp_path):
    log = AuditLog(tmp_path / "ledger.db")
    assert log._con.execute("SELECT count, hash FROM ledger_head").fetchone() == (0, GENESIS)
    assert log.verify() == VerifyResult(True, 0, None)


class _SignFails(RuntimeError):
    pass


def _failing_sign(*_):
    raise _SignFails


def test_failed_append_leaves_no_transaction_open(tmp_path, monkeypatch):
    # ROLLBACK -> None: TypeError replaces the real error and the transaction stays open, so the next
    # append nests into it and nothing reaches the file
    log = _ledger(tmp_path, 2)
    monkeypatch.setattr(log, "_sign", _failing_sign)
    with pytest.raises(_SignFails):
        _append(log)
    assert not log._con.in_transaction
    monkeypatch.undo()
    _append(log)
    other = sqlite3.connect(tmp_path / "ledger.db")
    assert other.execute("SELECT count(*) FROM ledger").fetchone() == (3,)


def test_failed_nested_append_keeps_the_outer_transaction(tmp_path, monkeypatch):
    # ROLLBACK TO / RELEASE ledger_append -> None or "XX...XX": the real error is lost, or the half-written
    # entry stays inside the order store's transaction
    log = _ledger(tmp_path, 1)
    con = log._con
    con.execute("BEGIN")
    monkeypatch.setattr(log, "_sign", _failing_sign)
    with pytest.raises(_SignFails):
        _append(log)
    assert con.in_transaction
    assert con.execute("SELECT count(*) FROM ledger").fetchone() == (1,)
    con.execute("COMMIT")
    monkeypatch.undo()
    assert log.verify() == VerifyResult(True, 1, None)


def test_head_hash_changed_on_a_short_ledger_points_at_the_last_entry(tmp_path):
    # min(count + 1, max(head count, 1)) -> max(head count, 2)
    log = _ledger(tmp_path, 1)
    log._con.execute("UPDATE ledger_head SET hash = ? WHERE id = 1", ("0" * 64,))
    assert log.verify() == VerifyResult(False, 1, 1)


def test_extra_field_with_a_matching_hash_breaks_the_chain_there(tmp_path):
    # `set(body) != FIELDS or stored_seq != expected` -> `and`: a body with a field more passes when its hash
    # is recomputed, and the break shows one entry later
    log = _ledger(tmp_path)
    seq, body, _ = _rows(log)[1]
    body = {**json.loads(body), "note": "added later"}
    log._con.execute("UPDATE ledger SET body = ?, hash = ? WHERE seq = ?", (json.dumps(body), entry_hash(body), seq))
    assert log.verify() == VerifyResult(False, 1, 2)


def test_signed_head_names_its_type_and_key(tmp_path):
    # "typ" / "kid" in the protected header renamed: a reader cannot tell a head from another kitchen JWS
    key = JWK.generate(kty="EC", crv="P-256")
    log = AuditLog(tmp_path / "ledger.db", key=key)
    _append(log)
    jws = JWS()
    jws.deserialize(log.head().signature)
    assert json.loads(jws.objects["protected"]) == {"alg": "ES256", "typ": HEAD_TYP, "kid": key.thumbprint()}


def test_head_from_before_the_signature_gets_its_columns(tmp_path):
    # ("at", "sig") -> ("XXatXX", ...): an old head table never gets the column, and every append fails
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE ledger (seq INTEGER PRIMARY KEY, order_id TEXT, body TEXT NOT NULL, hash TEXT NOT NULL)")
    con.execute("CREATE TABLE ledger_head (id INTEGER PRIMARY KEY CHECK (id = 1), count INTEGER NOT NULL, "
                "hash TEXT NOT NULL)")
    con.execute("INSERT INTO ledger_head VALUES (1, 0, ?)", (GENESIS,))
    con.commit()
    con.close()
    key = JWK.generate(kty="EC", crv="P-256")
    log = AuditLog(path, key=key)
    assert {r[1] for r in log._con.execute("PRAGMA table_info(ledger_head)")} == {"id", "count", "hash", "at", "sig"}
    assert log.verify() == VerifyResult(False, 0, 1)  # the old head is unsigned
    _append(log)
    assert log.verify() == VerifyResult(True, 1, None)


def test_tampered_entry_still_shows_as_plain_values():
    # the ledger page shows a tampered row as it is; every field falls back to an empty value of its type
    garbage = {"seq": "7", "at": None, "actor": None, "kind": None, "sentence": None, "facts": "ab",
               "mandate_id": None, "disclosed": [1], "rule_ids": "ab", "order_id": None, "prev_hash": None}
    e = _entry(json.dumps(garbage), "h")
    assert (e.seq, e.at, e.actor, e.kind, e.sentence, e.facts, e.mandate_id, e.disclosed, e.rule_ids,
            e.order_id, e.prev_hash, e.hash) == (0, "", "", "", "", [], None, {}, [], None, "", "h")
    for text in ("not json", "[1]"):
        e = _entry(text, "h")
        assert (e.sentence, e.seq, e.facts) == ("(this entry is not readable)", 0, [])


# policy/mandate.py: NonceStore

def test_nonce_exactly_ttl_old_survives_pruning():
    # prune with `<` instead of `<=`: a nonce exactly ttl old is still good in check()
    ns = NonceStore(ttl=timedelta(minutes=5))
    first = ns.issue(NOW)
    ns.issue(NOW + timedelta(minutes=5))  # prunes
    ns.check(first, NOW + timedelta(minutes=5))
    ns.consume(first, NOW + timedelta(minutes=5))


def test_consume_unknown_nonce_is_a_mandate_error():
    # pop(nonce) without a default raises KeyError, which would be a 500
    with pytest.raises(MandateError, match="^unknown or reused nonce$"):
        NonceStore().consume("never-issued", NOW)


def test_consume_stale_nonce_says_stale():
    ns = NonceStore(ttl=timedelta(minutes=5))
    n = ns.issue(NOW)
    with pytest.raises(MandateError, match="^stale nonce$"):
        ns.consume(n, NOW + timedelta(minutes=5, seconds=1))
    with pytest.raises(MandateError, match="^unknown or reused nonce$"):
        ns.consume(n, NOW)  # consumed even when stale


def test_nonce_store_limit_is_exact():
    # max_open 10000 -> 10001: the cap counts open nonces exactly
    ns = NonceStore(max_open=3)
    for _ in range(3):
        ns.issue(NOW)
    with pytest.raises(MandateError, match="too many open nonces"):
        ns.issue(NOW)
    assert NonceStore().max_open == 10000


def test_key_file_in_new_nested_folder(tmp_path):
    # mkdir(parents=False)
    path = tmp_path / "x" / "keys" / "kitchen.jwk"
    key = load_or_create_key(path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert load_or_create_key(path).thumbprint() == key.thumbprint()


# policy/mandate.py: error messages name the parser error class

def _verify(token, ns):
    return verify_presentation(token, kitchen_pub=KITCHEN, issuer=ISSUER, aud=AUDIENCE, nonces=ns, now=NOW)


def test_broken_disclosure_names_json_error():
    # type(e) -> type(None) in the ValueError branch
    ns = NonceStore()
    nonce, jwt, disc, _ = honest_parts(ns)
    disc = [*disc, b64(b"xx")]
    with pytest.raises(MandateError, match=r"^invalid Spend Pass \(JSONDecodeError\)$"):
        _verify("~".join([jwt, *disc, kb(jwt, disc, nonce)]), ns)


def test_non_list_sd_names_type_error():
    # type(e) -> type(None) in the catch-all branch
    payload = {"iss": ISSUER, "nbf": DEMO_CLAIMS["nbf"], "exp": DEMO_CLAIMS["exp"], "_sd_alg": "sha-256",
               "cnf": {"jwk": json.loads(AGENT.export_public())}, "_sd": 5}
    jwt = jws({"alg": "ES256", "typ": "example+sd-jwt"}, payload, KITCHEN)
    ns = NonceStore()
    nonce = ns.issue(NOW)
    with pytest.raises(MandateError, match=r"^invalid Spend Pass \(TypeError\)$"):
        _verify("~".join([jwt, kb(jwt, [], nonce)]), ns)


# policy/mandate.py: _mandate defaults for fields a pass leaves out

def test_mandate_defaults_fail_closed():
    m = _mandate({"nbf": 1, "exp": 2})
    assert (m.id, m.issuer, m.holder) == ("", "", "")
    assert m.split_max_extra_bp == 0
    assert m.split_allow_listed is False
    assert m.prefer_labels is None and m.diet is None
    assert (m.auto_limit_cents, m.hard_cap_cents) == (None, None)
    assert m.categories == () and m.deliver_by is None and m.substitutes is None


def test_mandate_keeps_disclosed_prefer_labels():
    # p.get("preferLabels") mutated, prefer_labels=None: an empty list stays an empty tuple, not None
    assert _mandate({"nbf": 1, "exp": 2, "preferLabels": []}).prefer_labels == ()
    assert _mandate({"nbf": 1, "exp": 2, "preferLabels": ["HEART"]}).prefer_labels == ("HEART",)
    m = _mandate({"nbf": 1, "exp": 2, "split": {"maxExtraCostPct": 2.5, "allowListedSubstitutes": True}})
    assert (m.split_max_extra_bp, m.split_allow_listed) == (250, True)


# policy/mandate.py: key binding parsing and the RFC 9901 disclosure check

def test_b64_strips_only_padding():
    # rstrip(b"=") -> rstrip(b"XX=XX"): a digest that ends in X would lose it
    assert _b64(b"\x00\x00\x17") == "AAAX"
    assert _b64(b"\x00") == "AA"


@pytest.mark.parametrize("token", ["no-tilde", "a~b", "a~x.e30", "a~x.WzFd.s", "a~x.eyJub25jZSI6MX0.s"])
def test_kb_payload_refusals_say_no_key_binding(token):
    # "e30" is {}, "WzFd" is [1], the last one has a nonce that is not a string
    with pytest.raises(MandateError, match="^no key binding$"):
        _kb_payload(token)


def test_digests_finds_sd_lists_and_array_items_at_any_depth():
    node = {"_sd": ["d1", 5], "a": [{"...": "d2"}, {"...": "d3", "x": 1}], "b": {"c": {"_sd": ["d4"]}}}
    out: set[str] = set()
    _digests(node, out)
    assert out == {"d1", "d2", "d4"}


def _disclosure(*parts) -> str:
    return b64(json.dumps(list(parts)).encode())


def _sha(d: str) -> str:
    return _b64(hashlib.sha256(d.encode("ascii")).digest())


def test_nested_disclosure_referenced_by_another_disclosure_is_accepted():
    inner = _disclosure("salt2", "city", "Espoo")
    outer = _disclosure("salt1", "address", {"_sd": [_sha(inner)]})
    jwt = f"{b64(b'{}')}.{b64(json.dumps({'_sd': [_sha(outer)]}).encode())}.sig"
    _check_disclosures(f"{jwt}~{outer}~{inner}~kb")
    stray = _disclosure("salt3", "autoLimitCents", 999999)
    with pytest.raises(MandateError, match="^disclosure not part of the Spend Pass$"):
        _check_disclosures(f"{jwt}~{outer}~{inner}~{stray}~kb")


# policy/mandate.py: the key binding's own iat window is inclusive at both ends, and revocation sees the jti

def _with_kb_iat(iat: int, ns: NonceStore, **kw):
    nonce, jwt, disc, _ = honest_parts(ns)
    token = "~".join([jwt, *disc, kb(jwt, disc, nonce, iat=iat)])
    return verify_presentation(token, kitchen_pub=KITCHEN, issuer=ISSUER, aud=AUDIENCE, nonces=ns, now=NOW, **kw)


@pytest.mark.parametrize("offset", [-600, 60])
def test_kb_iat_at_the_edges_is_accepted(offset):
    # `ts - 10 min <= iat` -> `<`, `iat <= ts + 60 s` -> `<`
    assert _with_kb_iat(int(NOW.timestamp()) + offset, NonceStore()).id == "M-1"


@pytest.mark.parametrize("offset", [-601, 61])
def test_kb_iat_outside_the_edges_is_refused(offset):
    with pytest.raises(MandateError, match="^key binding signed at the wrong time$"):
        _with_kb_iat(int(NOW.timestamp()) + offset, NonceStore())


def test_revocation_is_asked_about_the_pass_jti():
    asked = []
    with pytest.raises(MandateError, match="^Spend Pass M-1 was revoked by the kitchen$"):
        _with_kb_iat(int(NOW.timestamp()), NonceStore(), revoked=lambda jti: asked.append(jti) or True)
    assert asked == ["M-1"]


# policy/mandate.py: the pass's own iat, a missing jti, the key binding's default time

def _pass(**claims):
    return issue_mandate({**DEMO_CLAIMS, **claims}, DEMO_SD_FIELDS, KITCHEN, AGENT)


def _present(issuance, ns, **kw):
    _, jwt, disc, kbjwt = honest_parts(ns, issuance=issuance)
    token = "~".join([jwt, *disc, kbjwt])
    return verify_presentation(token, kitchen_pub=KITCHEN, issuer=ISSUER, aud=AUDIENCE, nonces=ns, now=NOW, **kw)


def test_pass_iat_that_is_not_a_number_is_refused():
    # `iat is not None and type(iat) is not int` -> `iat is None and ...`: a string iat reaches `iat > ts`
    with pytest.raises(MandateError, match="^Spend Pass without validity window$"):
        _present(_pass(iat="2026-11-14"), NonceStore())


def test_pass_iat_one_skew_ahead_is_accepted_one_more_second_is_not():
    # `iat > ts + skew` -> `>=`
    ts = int(NOW.timestamp())
    assert _present(_pass(iat=ts + 60), NonceStore()).id == "M-1"
    with pytest.raises(MandateError, match="^Spend Pass issued in the future$"):
        _present(_pass(iat=ts + 61), NonceStore())


def test_pass_without_jti_asks_revocation_about_the_empty_id():
    # payload.get("jti", "") -> None / "XXXX": revocation is asked about "None" instead of ""
    asked = []
    claims = {k: v for k, v in DEMO_CLAIMS.items() if k != "jti"}
    issuance = issue_mandate(claims, DEMO_SD_FIELDS, KITCHEN, AGENT)
    assert _present(issuance, NonceStore(), revoked=lambda jti: asked.append(jti) or False).id == ""
    assert asked == [""]


def test_key_binding_without_iat_is_signed_now():
    # `int(time.time()) if iat is None else iat` -> always iat: the key binding carries "iat": null
    token = present(_pass(), {"diet"}, AGENT, AUDIENCE, "n-1")
    kb_payload = json.loads(base64.urlsafe_b64decode(token.split("~")[-1].split(".")[1] + "=="))
    assert abs(kb_payload["iat"] - time.time()) < 5
