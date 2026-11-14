"""The kitchen's own 6 digit approval code, kept hashed (scrypt, stdlib) in the kitchen's store.

Which code counts, first match wins: the code this kitchen set (signup or Settings), the demo code 246810 on
a demo copy, VALIDIO_APPROVE_CODE for the single kitchen of `make dev` and the tests."""

import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path

DEMO_CODE = "246810"  # demo copies only; the demo bar shows it on purpose
KEY = "approval_code_hash"
_N, _R, _P = 2**14, 8, 1


def hash_code(code: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(code.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def matches(stored: str, given: str | None) -> bool:
    try:
        _alg, salt, want = stored.split("$")
        h = hashlib.scrypt((given or "").encode(), salt=bytes.fromhex(salt), n=_N, r=_R, p=_P, dklen=32)
    except ValueError:
        return False
    return hmac.compare_digest(h.hex(), want)


def stored(path: Path) -> str | None:
    con = sqlite3.connect(path)
    try:
        row = con.execute("select value from demo_state where key = ?", (KEY,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    finally:
        con.close()
    return row[0] if row else None


def store(path: Path, code: str) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("insert or replace into demo_state values (?, ?)", (KEY, hash_code(code)))
        con.commit()
    finally:
        con.close()
