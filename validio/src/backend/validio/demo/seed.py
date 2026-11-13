"""Demo seed. `make seed` resets the local store to one fixed state, so every run shows the same numbers.

Frozen clock, kitchen hotel-espoo with its key and Spend Pass M-1, 8 weeks of simulated order history and the
stock-out switch for 466375 (off after a reset). The planted line on 463047 lives in the catalog index
(`planted` table, from demo/planted.json) and is not touched here.
"""

import json
import os
import secrets
import sqlite3
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from ..config import DATA
from ..policy.mandate import (
    AUDIENCE,
    DEMO_CLAIMS,
    DEMO_SD_FIELDS,
    Mandate,
    NonceStore,
    issue_mandate,
    load_or_create_key,
    present,
    verify_presentation,
)
from ..standing.model import History, PastOrder
from ..valio.models import Availability

HERE = Path(__file__).resolve().parent
HISTORY_FILE = HERE / "history.json"
NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")  # Saturday 14 November 10:00 Helsinki
KITCHEN = "hotel-espoo"
SPEND_PASS_ID = "M-1"
STOCKOUT_ID = "466375"
STOCKOUT_NOTE = "Simulated stock-out: Valio really has stock, the demo button sets it to zero."
UNIT_WORDS = {"BAG": "bags", "KI": "cartons", "ST": "packs"}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

SCHEMA = """
create table kitchen (id text primary key, name text);
create table spend_pass (id text primary key, kitchen_id text, issuance text);
create table demo_state (key text primary key, value text);
create table past_order (delivered text primary key, kitchen_id text, guests integer, simulated integer);
create table past_line (delivered text, product_id text, sales_qty integer, primary key (delivered, product_id));
"""


def db_path() -> Path:
    return Path(os.environ.get("VALIDIO_DB") or DATA / "validio.db")


def keys_path() -> Path:
    return Path(os.environ.get("VALIDIO_KEYS") or DATA / "keys")


def load_history(path: Path = HISTORY_FILE) -> History:
    x = json.loads(Path(path).read_text())
    sim = bool(x["simulated"])
    return History(
        kitchen=x["kitchen"], weekday=WEEKDAYS.index(x["weekday"]),
        diet={pid: tuple(v["diet"]) for pid, v in x["lines"].items()},
        weeks=[PastOrder(date.fromisoformat(w["delivered"]), int(w["guests"]),
                         {k: int(v) for k, v in w["lines"].items()}, sim) for w in x["weeks"]],
        simulated=sim, note=x.get("note", ""),
    )


def kitchen_key(keys_dir: Path | None = None):
    """The kitchen's private key: it signs the Spend Pass and the Open Ledger head."""
    return load_or_create_key(Path(keys_dir or keys_path()) / "kitchen-es256.json")


def reset(path: Path | None = None, keys_dir: Path | None = None) -> Path:
    """Drop every table in the local store, then write the seed. Keys are kept when they exist, so a reset
    never invalidates a pass an agent already holds. Stores that keep a connection open must reopen it."""
    path, keys_dir = Path(path or db_path()), Path(keys_dir or keys_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    kitchen_key = load_or_create_key(keys_dir / "kitchen-es256.json")
    agent_key = load_or_create_key(keys_dir / "agent-es256.json")
    con = sqlite3.connect(path, isolation_level=None)
    try:
        con.execute("begin immediate")
        for (name,) in con.execute("select name from sqlite_master where type = 'table'").fetchall():
            if not name.startswith("sqlite_"):
                con.execute(f'drop table "{name}"')
        for stmt in SCHEMA.strip().split(";"):
            if stmt.strip():
                con.execute(stmt)
        con.execute("insert into kitchen values (?, ?)", (KITCHEN, "Hotel kitchen in Espoo"))
        issuance = issue_mandate(DEMO_CLAIMS, DEMO_SD_FIELDS, kitchen_key, agent_key)
        con.execute("insert into spend_pass values (?, ?, ?)", (SPEND_PASS_ID, KITCHEN, issuance))
        con.execute("insert into demo_state values ('stockout_466375', '0')")
        con.execute("insert into demo_state values ('seed_token', ?)", (secrets.token_hex(8),))
        h = load_history()
        for w in h.weeks:
            d = w.delivered.isoformat()
            con.execute("insert into past_order values (?, ?, ?, ?)", (d, h.kitchen, w.guests, int(w.simulated)))
            con.executemany("insert into past_line values (?, ?, ?)", [(d, p, q) for p, q in w.lines.items()])
        con.execute("commit")
    except BaseException:
        con.execute("rollback")
        raise
    finally:
        con.close()
    return path


def dump(path: Path) -> dict[str, list]:
    """Every seeded row except the pass signature (ES256 signs with a fresh random value each time) and the
    seed token."""
    con = sqlite3.connect(path)
    try:
        return {
            t: con.execute(f"select * from {t} order by 1").fetchall()
            for t in ("kitchen", "past_order", "past_line")
        } | {
            "demo_state": con.execute("select * from demo_state where key != 'seed_token' order by 1").fetchall(),
            "spend_pass": con.execute("select id, kitchen_id from spend_pass").fetchall(),
        }
    finally:
        con.close()


def seed_token(path: Path | None = None) -> str | None:
    """Changes with every reset. None when the store was never seeded."""
    path = Path(path or db_path())
    if not path.is_file():
        return None
    con = sqlite3.connect(path)
    try:
        row = con.execute("select value from demo_state where key = 'seed_token'").fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        con.close()
    return row[0] if row else None


def stockout(path: Path | None = None) -> bool:
    con = sqlite3.connect(path or db_path())
    try:
        row = con.execute("select value from demo_state where key = 'stockout_466375'").fetchone()
    finally:
        con.close()
    return bool(row and row[0] == "1")


def set_stockout(path: Path | None, on: bool) -> None:
    con = sqlite3.connect(path or db_path())
    try:
        con.execute("update demo_state set value = ? where key = 'stockout_466375'", ("1" if on else "0",))
        con.commit()
    finally:
        con.close()


def real_stock(valio, day: date | None = None) -> tuple[float, str] | None:
    """What Valio answers for 466375 on the Spend Pass's delivery day, before the demo switch sets it to
    zero: (quantity, sales unit). None when Valio (or the recording) has no answer."""
    import httpx

    from ..valio.budget import CallBudget
    from ..valio.client import ReplayMiss

    day = day or date.fromisoformat(DEMO_CLAIMS["deliverBy"])
    try:
        a = valio.availability([STOCKOUT_ID], day, CallBudget()).get(STOCKOUT_ID)
    except (ReplayMiss, httpx.HTTPError):  # no recording or a failed call: the note says "has stock"
        return None
    if a is None or not a.lines or a.amount is None:
        return None
    return a.amount, a.lines[0].sales_unit


def stockout_note(stock: tuple[float, str] | None, lead: str = "Simulated stock-out:") -> str:
    if stock is None:
        return STOCKOUT_NOTE if lead == "Simulated stock-out:" else \
            f"{lead} Valio really has it in stock, the demo button sets it to zero."
    qty, unit = stock
    n = f"{int(qty):,}" if float(qty).is_integer() else f"{qty:,}"
    return f"{lead} Valio really has {n} {UNIT_WORDS.get(unit, unit.lower())}; the demo sets it to zero."


def apply_stockout(avail: dict[str, Availability], on: bool) -> dict[str, Availability]:
    """With the switch on, 466375 keeps its delivery date and cut-off but has 0 in stock."""
    a = avail.get(STOCKOUT_ID)
    if not on or a is None:
        return avail
    lines = [replace(ln, amount=0.0) for ln in a.lines]
    return {**avail, STOCKOUT_ID: replace(a, lines=lines)}


def spend_pass(path: Path | None = None, keys_dir: Path | None = None,
               disclose: set[str] | frozenset[str] = frozenset({"autoLimitCents", "hardCapCents", "diet"}),
               now: datetime = NOW) -> Mandate:
    """The seeded pass M-1 as Validio sees it after the agent shows `disclose`."""
    keys_dir = Path(keys_dir or keys_path())
    con = sqlite3.connect(path or db_path())
    try:
        (issuance,) = con.execute("select issuance from spend_pass where id = ?", (SPEND_PASS_ID,)).fetchone()
    finally:
        con.close()
    kitchen = load_or_create_key(keys_dir / "kitchen-es256.json")
    agent = load_or_create_key(keys_dir / "agent-es256.json")
    nonces = NonceStore()
    token = present(issuance, set(disclose), agent, AUDIENCE, nonces.issue(now), int(now.timestamp()))
    return verify_presentation(token, kitchen_pub=kitchen, issuer=DEMO_CLAIMS["iss"], aud=AUDIENCE,
                               nonces=nonces, now=now)
