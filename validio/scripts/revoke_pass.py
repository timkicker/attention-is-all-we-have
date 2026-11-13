"""Revoke a Spend Pass: `make revoke PASS=M-1`. Writes the kitchen's revocation list in data/validio.db and one
ledger entry. A running server sees it on the next presentation; nothing needs a restart."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
from validio.audit.log import AuditLog
from validio.config import load_settings
from validio.demo import seed
from validio.orders.service import revoke_pass
from validio.orders.store import Store


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pass_id", help="the Spend Pass id (its jti), e.g. M-1")
    pass_id = ap.parse_args(argv).pass_id.strip()
    if not pass_id:
        print("revoke: give a Spend Pass id, e.g. make revoke PASS=M-1")
        return 2
    path = seed.db_path()
    if seed.seed_token(path) is None:
        print(f"revoke: {path} holds no seeded store, run make seed first")
        return 2
    store, audit = Store(path), AuditLog(path, seed.kitchen_key())
    try:
        if revoke_pass(store, audit, pass_id, load_settings().now):
            print(f"revoked Spend Pass {pass_id}: every presentation and approve under it is refused now")
        else:
            print(f"Spend Pass {pass_id} was already revoked")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
