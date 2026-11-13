"""`make demo-check`: the demo scenes end to end through the agent API, no human, no key, no network.

The kitchen's agent (its fixed twin) talks MCP over HTTP to a Validio server on 127.0.0.1, the owner's
tap and the presenter's buttons go through the web app API. Every number is checked against the
blueprint's demo script. Each round starts from a reset; two rounds by default. Ends with ALL SCENES OK.

Without --base it starts its own server on 127.0.0.1:8418 with its own store under artifacts/, so a
running `make demo` is not touched. With --base it checks that server (VALIDIO_DEMO_TOKEN and
VALIDIO_APPROVE_CODE from the environment or .env).
"""

import argparse
import asyncio
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "backend"))
from validio.agent.buyer import run_scene
from validio.agent.holder import Holder
from validio.agent.llm import FakeLLM
from validio.agent.port import McpPort
from validio.audit.log import AuditLog
from validio.config import DEFAULT_ENV, _read_env_file

MAX_IDS = 40
SCENE2_SENTENCE = ("for 1010.00 EUR without a human. Stock quantity attested by Valio, contract price until "
                   "31 Dec 2026, delivery 16 Nov. Inside mandate M-1 (auto limit disclosed: 1200.00 EUR). "
                   "Valio reports 9999999999 for 464306, a placeholder, not a real count; treated as in stock.")


class Fail(AssertionError):
    pass


def check(cond, what: str):
    if not cond:
        raise Fail(what)


class Run:
    def __init__(self, base: str, db: Path, keys: Path, token: str, code: str, verbose: bool):
        self.base, self.db, self.keys, self.token, self.code, self.verbose = base, db, keys, token, code, verbose
        self.http = httpx.Client(base_url=base, timeout=30)

    def get(self, path: str):
        r = self.http.get(path)
        check(r.status_code == 200, f"GET {path} answered {r.status_code}: {r.text[:200]}")
        return r.json()

    def post(self, path: str, **kw):
        r = self.http.post(path, **kw)
        check(r.status_code == 200, f"POST {path} answered {r.status_code}: {r.text[:200]}")
        return r.json()

    def demo(self, action: str):
        return self.post(f"/api/demo/{action}", headers={"X-Demo-Token": self.token})

    async def agent(self, scene: int):
        holder = Holder.from_seed(lambda: self.get("/agent/v1/nonce")["nonce"], self.db, self.keys)
        on_event = None
        if self.verbose:
            def on_event(e):
                print(f"    agent {e.kind:6} {e.name}: {str(e.data)[:110]}")
        async with McpPort(f"{self.base}/mcp/", spend_pass=holder.presentation) as port:
            t = await run_scene(scene, FakeLLM(scene), port, on_event=on_event)
        answers = {}
        for e in t.events:
            if e.kind == "answer":
                check("error" not in e.data, f"scene {scene}: {e.name} failed: {e.data}")
                answers[e.name] = e.data
        return t, answers

    def ids_ok(self, req: dict, scene: int):
        live = req["liveChecked"]
        check(live["ids"] <= MAX_IDS and max(live["idsPerCall"] or [0]) <= MAX_IDS,
              f"scene {scene}: {live['ids']} ids live, per call {live['idsPerCall']}, the limit is {MAX_IDS}")
        return live

    # scenes

    async def scene1(self):
        _, a = await self.agent(1)
        check("search_products" in a and a["search_products"], "scene 1: product search gave nothing")
        req = a["request_supply"]
        check(req["decision"]["outcome"] == "auto_order", f"scene 1: decision {req['decision']}")
        inbox = self.get("/api/inbox")
        check([(i["id"], i["status"]) for i in inbox] == [(req["id"], "working")], f"scene 1: inbox {inbox}")
        sp = self.get("/api/spend-passes/M-1")
        check((sp["autoLimitCents"], sp["hardCapCents"], sp["diet"]) == (120000, 200000, ["lactose free"]),
              f"scene 1: Spend Pass card {sp}")
        check("approvers" in sp["hidden"] and "approvers" not in sp["disclosed"], "scene 1: approvers shown")
        live = self.ids_ok(req, 1)
        return f"request {req['id']} arrived, Spend Pass card 1200.00 EUR alone, 2000.00 EUR cap, lactose free, " \
               f"checked {live['ids']} products live"

    async def scene2(self):
        t, a = await self.agent(2)
        req, order = a["request_supply"], a["get_order"]
        check(order["state"] == "placed" and order["totalCents"] == 101000, f"scene 2: order {order}")
        check([(ln["productId"], ln["quantity"], ln["unit"]) for ln in order["lines"]] == [("464306", 1000, "ST")],
              f"scene 2: order lines {order['lines']}")
        req = self.get(f"/api/requests/{req['id']}")
        check(req["status"] == "ordered_alone", f"scene 2: status {req['status']}")
        live = self.ids_ok(req, 2)
        check(live["ids"] <= 12, f"scene 2: {live['ids']} ids live, at most 12 candidates")
        opts = {o["productId"]: o for o in req["lines"][0]["options"]}
        expect = {"464306": "chosen", "464401": "ranked", "462921": "blocked", "462703": "rejected",
                  "463047": "rejected", "469541": "rejected"}
        for pid, verdict in expect.items():
            check(pid in opts and opts[pid]["verdict"] == verdict,
                  f"scene 2: {pid} should be {verdict}, is {opts.get(pid, {}).get('verdict')}")
        check(opts["464401"]["totalCents"] == 110000, "scene 2: 464401 should cost 1100.00 EUR")
        check(opts["462921"]["totalCents"] == 219400 and "hard cap" in opts["462921"]["sentence"],
              f"scene 2: 462921 {opts['462921']['sentence']}")
        check("cooking fat mix" in opts["462703"]["sentence"], f"scene 2: 462703 {opts['462703']['sentence']}")
        for pid in ("463047", "469541"):
            check("Low lactose is not lactose free" in opts[pid]["sentence"], f"scene 2: {pid} {opts[pid]['sentence']}")
        planted = opts["463047"].get("supplierText") or {}
        check(planted.get("planted") and planted.get("grade") == "untrusted"
              and any(f["code"] == "addresses_agents" for f in planted.get("reader", {}).get("flags", [])), f"scene 2: planted line {planted}")
        led = self.get("/api/ledger")["entries"]
        sentence = next((e["sentence"] for e in led if e["kind"] == "order" and e["orderId"] == order["id"]), "")
        check(sentence.startswith("Ordered 1000 ST of 464306 ") and sentence.endswith(SCENE2_SENTENCE),
              f"scene 2: ledger sentence {sentence!r}")
        check(t.final.endswith("is placed."), f"scene 2: agent said {t.final!r}")
        return f"464306 ordered alone, 1000 ST for 1010.00 EUR, 462921 blocked at 2194.00 EUR, planted line " \
               f"on 463047 ignored, checked {live['ids']} products live"

    async def scene3(self):
        check(self.demo("stock-out") == {"stockOut466375": True}, "scene 3: stock-out switch")
        _, a = await self.agent(3)
        req = self.get(f"/api/requests/{a['request_supply']['id']}")
        check(req["status"] == "waiting" and req["decision"]["outcome"] == "ask_human",
              f"scene 3: {req['status']} {req['decision']}")
        check(any("stock-out" in s["what"] for s in req.get("simulated") or []), "scene 3: stock-out not labelled")
        self.ids_ok(req, 3)
        line = req["lines"][0]
        subs = {o["productId"]: o["verdict"] for o in line["substitutes"]}
        check(subs == {"466151": "blocked", "468526": "blocked", "475908": "blocked", "473986": "not_deliverable"},
              f"scene 3: listed substitutes {subs}")
        # the real data ranks the mozzarella-fontal blend (0 g lactose) first; it is cheaper than 463383
        check(line["chosen"] == {"productId": "465256", "salesQty": 10, "isSubstitute": True, "onValioList": False},
              f"scene 3: Safe Swap chose {line['chosen']}, expected 465256 x 10")
        pick = next((o for o in line.get("beyondList") or [] if o["productId"] == "465256"), {})
        check("mozzarella-fontal blend" in pick.get("sentence", "") and "465256" in (line.get("swapSentence") or ""),
              f"scene 3: 465256 explained as {pick.get('sentence')!r}, swap sentence {line.get('swapSentence')!r}")
        order = self.get(f"/api/orders/{req['orderId']}")
        check(order["state"] == "waiting" and order["totalCents"] == 18010, f"scene 3: order {order['state']} "
              f"{order['totalCents']}")
        check(req.get("question", "").endswith("?"), "scene 3: no question for the owner")
        r = self.http.post(f"/api/orders/{order['id']}/approve", json={"code": self.code})
        check(r.status_code == 200, f"scene 3: approve answered {r.status_code} {r.text[:200]}")
        done = r.json()
        check(done["state"] == "placed" and [h["state"] for h in done["history"]] == ["waiting", "approved", "placed"],
              f"scene 3: after approve {done['state']} {done['history']}")
        again = self.http.post(f"/api/orders/{order['id']}/approve", json={"code": self.code})
        check(again.status_code == 409, f"scene 3: second approve answered {again.status_code}")
        check(self.get(f"/api/requests/{req['id']}")["status"] == "ordered", "scene 3: request not ordered")
        placed = [e["sentence"] for e in self.get("/api/ledger")["entries"]
                  if e["kind"] == "order" and e["orderId"] == order["id"]]
        check(len(placed) == 1 and "after the owner approved" in placed[0] and "without a human" not in placed[0],
              f"scene 3: order sentence {placed}")
        return "3 listed substitutes blocked for lactose, 473986 not deliverable, 465256 blend 10 for 180.10 EUR " \
               "approved by the owner, a second approve refused"

    async def scene4(self):
        (summary,) = self.get("/api/steady")
        check(summary["id"] == "S-1", f"scene 4: {summary}")
        before = self.get("/api/steady/S-1")
        check(before["simulatedHistory"] is True, "scene 4: history not labelled simulated")
        got = {ln["productId"]: ln for ln in self.post("/api/steady/S-1/renew")["lines"]}
        milk, parm, pan, mozz = got["464306"], got["463968"], got["471376"], got["466375"]
        check((milk["result"], milk["thisWeekQuantity"], milk["totalCents"]) == ("renewed", 300, 30300),
              f"scene 4: milk {milk['result']} {milk.get('thisWeekQuantity')} {milk.get('totalCents')}")
        check((parm["result"], parm["thisWeekQuantity"], parm["totalCents"]) == ("split_renewed", 177, 77249)
              and parm["split"]["extraCostPct"] == 2.5, f"scene 4: parmesan {parm['result']} {parm.get('totalCents')}")
        check((pan["result"], pan["thisWeekQuantity"]) == ("waiting", 27) and "wheat" in pan["sentence"],
              f"scene 4: pancakes {pan['result']} {pan['sentence']}")
        check(mozz["result"] == "flagged" and ("per_guest_up", 26) in [(f["kind"], f.get("pct")) for f in mozz["flags"]],
              f"scene 4: mozzarella {mozz['result']} {mozz['flags']}")
        acc = {ln["productId"]: ln for ln in self.post("/api/steady/S-1/lines/471376/accept")["lines"]}
        check(acc["471376"]["result"] == "accepted", f"scene 4: pancakes after accept {acc['471376']['result']}")
        return "milk renewed alone, parmesan split 177 for 772.49 EUR (2.5 % more), pancakes waited and the chef " \
               "ordered 27, mozzarella flagged 26 % more per guest"

    async def scene5(self):
        led = self.get("/api/ledger")
        chain = led["chain"]
        check(chain["ok"] and chain["count"] == len(led["entries"]) > 0, f"scene 5: chain {chain}")
        check(all(e["sentence"] for e in led["entries"]), "scene 5: an entry without a sentence")
        text = str(led)
        check("owner:anna" not in text and "approvers" not in text, "scene 5: the approver list reached the ledger")
        # one changed letter breaks the chain: on a copy, never on the live store
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "copy.db"
            shutil.copy(self.db, copy)
            con = sqlite3.connect(copy)
            seq, body = con.execute("select seq, body from ledger order by seq limit 1 offset 1").fetchone()
            entry = json.loads(body)
            entry["sentence"] = entry["sentence"].replace(entry["sentence"][-2], "X", 1)  # one changed letter
            con.execute("update ledger set body = ? where seq = ?", (json.dumps(entry), seq))
            con.commit()
            con.close()
            broken = AuditLog(copy).verify()
        check(not broken.ok and broken.broken_at == seq, f"scene 5: tampered copy verified as {broken}")
        return f"chain verified, {chain['count']} entries, one changed entry caught at #{seq}"

    async def round(self, scenes: list[int]) -> None:
        self.demo("reset")
        check(self.get("/api/ledger")["chain"]["count"] == 0, "reset left ledger entries")
        for n in scenes:
            msg = await getattr(self, f"scene{n}")()
            print(f"  scene {n} OK: {msg}")


def env() -> dict[str, str]:
    return {**_read_env_file(DEFAULT_ENV), **os.environ}


def start_server(port: int, store: Path, token: str, code: str) -> subprocess.Popen:
    e = {**os.environ, "VALIDIO_DB": str(store / "validio.db"), "VALIDIO_DEMO_TOKEN": token,
         "VALIDIO_APPROVE_CODE": code, "VALIO_MODE": "replay", "VALIDIO_DEMO": "1"}
    log = open(store / "server.log", "w")  # noqa: SIM115  (the server writes it until it stops)
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "validio.api.app:app", "--host", "127.0.0.1",
                          "--port", str(port)], cwd=ROOT / "src" / "backend", env=e, stdout=log, stderr=log)
    for _ in range(100):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=1).status_code == 200:
                return p
        except httpx.HTTPError:
            pass
        if p.poll() is not None:
            break
        time.sleep(0.2)
    p.terminate()
    raise SystemExit(f"server did not start, see {store / 'server.log'}")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="check a running server instead of starting one")
    ap.add_argument("--scenes", default="1,2,3,4,5")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("-v", "--verbose", action="store_true", help="print the agent's tool calls")
    args = ap.parse_args()
    scenes = [int(s) for s in args.scenes.split(",")]
    keys = Path(env().get("VALIDIO_KEYS") or ROOT / "data" / "keys")
    proc = None
    if args.base:
        base, db = args.base.rstrip("/"), Path(env().get("VALIDIO_DB") or ROOT / "data" / "validio.db")
        token, code = env().get("VALIDIO_DEMO_TOKEN", ""), env().get("VALIDIO_APPROVE_CODE", "")
    else:
        store = ROOT / "artifacts" / "demo-check"
        store.mkdir(parents=True, exist_ok=True)
        token, code = secrets.token_urlsafe(16), f"{secrets.randbelow(10**6):06d}"
        proc = start_server(8418, store, token, code)
        base, db = "http://127.0.0.1:8418", store / "validio.db"
    try:
        for i in range(args.rounds):
            print(f"round {i + 1} from a reset, scenes {args.scenes}")
            await Run(base, db, keys, token, code, args.verbose).round(scenes)
    except Fail as e:
        print(f"FAILED: {e}")
        return 1
    finally:
        if proc:
            proc.terminate()
            proc.wait(10)
    print("ALL SCENES OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
