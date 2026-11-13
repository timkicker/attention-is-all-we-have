"""The order store shares one SQLite connection between the server's worker threads. Reads and writes
from many threads at once must not break it (the load test at 50 agents hit "no more rows available")."""

import threading

from validio.orders.store import Store


def test_concurrent_reads_and_writes_share_the_connection(tmp_path):
    store = Store(tmp_path / "s.db")
    errors: list[BaseException] = []

    def work(i: int) -> None:
        try:
            for k in range(150):
                r = store.new_request({"agent": f"a{i}", "k": k})
                assert store.request(r["id"])["k"] == k
                o = store.new_order({"requestId": r["id"]})
                assert store.order(o["id"])["requestId"] == r["id"]
                store.idem_put("t", f"{i}-{k}", "h", r["id"])
                assert store.idem_get("t", f"{i}-{k}") == ("h", r["id"])
                store.remember_pass(f"p{i}", {"k": k})
                assert store.seen_pass(f"p{i}") is not None
                if k % 50 == 0:
                    store.requests(), store.orders()
        except BaseException as e:  # noqa: BLE001 - collected and re-raised in the main thread
            errors.append(e)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, repr(errors[:3])
    assert len(store.requests()) == 16 * 150


def test_concurrent_ledger_appends_keep_the_chain(tmp_path):
    from datetime import UTC, datetime

    from validio.audit.log import AuditLog

    log = AuditLog(tmp_path / "a.db")
    errors: list[BaseException] = []

    def work(i: int) -> None:
        try:
            for k in range(60):
                log.append(at=datetime(2026, 11, 14, tzinfo=UTC), actor=f"a{i}", kind="decision",
                           sentence=f"{i}-{k}", facts=[], mandate_id="M-1", disclosed={}, rule_ids=[],
                           order_id=f"O-{i}")
                if k % 20 == 0:
                    log.list(order_id=f"O-{i}"), log.verify()
        except BaseException as e:  # noqa: BLE001 - collected and re-raised in the main thread
            errors.append(e)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, repr(errors[:3])
    ok, count, broken_at = log.verify()
    assert (ok, count, broken_at) == (True, 12 * 60, None)
