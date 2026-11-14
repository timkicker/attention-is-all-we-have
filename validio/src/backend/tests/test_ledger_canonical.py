"""The ledger's canonical JSON is RFC 8785 (JCS) for what entries hold. No Valio data needed."""

from datetime import datetime

from validio.audit.log import AuditLog, canonical, entry_hash

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")


def test_canonical_matches_jcs_vectors():
    # RFC 8785 rules on our subset: sorted keys, no whitespace, literal UTF-8, \\u escapes only for controls
    assert canonical({"b": 1, "a": [True, None, "ä€"], "c": "line\nbreak"}) == \
        '{"a":[true,null,"ä€"],"b":1,"c":"line\\nbreak"}'


def test_floats_never_enter_an_entry(tmp_path):
    log = AuditLog(tmp_path / "l.db")
    e = log.append(at=NOW, actor="validio", kind="decision", sentence="s",
                   facts=[{"field": "x", "value": 2.0}, {"field": "y", "value": 0.1}],
                   mandate_id=None, disclosed={"pct": 5.0}, rule_ids=[], order_id=None)
    assert e.facts == [{"field": "x", "value": 2}, {"field": "y", "value": "0.1"}] and e.disclosed == {"pct": 5}
    assert log.verify().ok
    body = {k: v for k, v in e.as_dict().items() if k != "hash"}
    assert entry_hash(body) == e.hash
