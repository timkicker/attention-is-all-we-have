"""Load test: N fake agents, each with its own Holder, run scene 2 at the same time against a local server.

    cd validio/src/backend && uv run python ../../scripts/loadtest.py --agents 1 10 50 --rounds 5

For every N it seeds a fresh store in a temporary folder and starts its own uvicorn on a free port in
replay mode (no network, never Valio's servers). Each agent runs scene 2 `rounds` times, one after the
other: nonce, POST /agent/v1/requests, nonce, POST /agent/v1/orders, GET /agent/v1/orders/{id}.

The client measures latency per route, throughput and errors. The server process counts what it cannot
see from outside: time spent waiting for the locks in front of the SQLite connections, "database is
locked" errors, and every question to Valio (ids per call, calls and ids per request).
With --json it also writes the raw numbers next to the printed table."""

import argparse
import asyncio
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "backend"))

MILK = "1000 litres of lactose-free milk by Monday, budget 1200 euro"
MIXES = {  # scene 2, and a five-line request that sends 26 distinct ids to Valio (the cap is 40)
    "scene2": [{"text": MILK}],
    "wide": [{"text": "1000 litres of lactose-free milk"}, {"productId": "466375", "quantity": 200, "unit": "BAG"},
             {"productId": "463968", "quantity": 200, "unit": "ST"},
             {"productId": "471376", "quantity": 30, "unit": "KAR"}, {"text": "lactose-free mozzarella 20 kg"}],
}


# ---------------------------------------------------------------- server side (child process)

class TimedRLock:
    """An RLock that adds up how long callers waited for it."""

    def __init__(self, name: str, stats: dict):
        self._lock, self.name, self.stats = threading.RLock(), name, stats

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        if self._lock.acquire(blocking=False):
            self.stats[self.name]["acquired"] += 1
            return True
        if not blocking:
            return False
        t = time.perf_counter()
        ok = self._lock.acquire(timeout=timeout)
        s = self.stats[self.name]
        s["acquired"] += ok
        s["waits"] += 1
        s["wait_s"] += time.perf_counter() - t
        s["max_wait_s"] = max(s["max_wait_s"], time.perf_counter() - t)
        return ok

    def release(self) -> None:
        self._lock.release()

    __enter__ = acquire

    def __exit__(self, *exc) -> None:
        self.release()


def serve(port: int, stats_file: Path) -> None:
    import sqlite3

    import uvicorn

    from validio.api import steady
    from validio.orders import service, store
    from validio.valio import budget, client

    locks: dict = defaultdict(lambda: {"acquired": 0, "waits": 0, "wait_s": 0.0, "max_wait_s": 0.0})
    valio = {"per_call": [], "budgets": [], "db_locked": 0}

    def wrap_init(cls, attr, name):
        orig = cls.__init__

        def init(self, *a, **kw):
            orig(self, *a, **kw)
            setattr(self, attr, TimedRLock(name, locks))
        cls.__init__ = init

    wrap_init(store.Store, "_lock", "order store connection")
    wrap_init(service.OrderService, "lock", "order service")
    steady.runtime.lock = TimedRLock("steady runtime", locks)

    orig_replay = client.ValioClient._replay

    def replay(self, endpoint, requested, part):
        valio["per_call"].append([endpoint, len(part)])
        return orig_replay(self, endpoint, requested, part)
    client.ValioClient._replay = replay

    orig_budget = budget.CallBudget.__init__

    def budget_init(self, *a, **kw):
        orig_budget(self, *a, **kw)
        valio["budgets"].append(self)
    budget.CallBudget.__init__ = budget_init

    from validio.api.app import app

    @app.exception_handler(sqlite3.OperationalError)
    def locked(_req, exc):
        from fastapi.responses import JSONResponse
        if "locked" in str(exc):
            valio["db_locked"] += 1
        return JSONResponse({"detail": str(exc)}, status_code=500)

    try:  # uvicorn raises the SIGINT again after its clean shutdown
        uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")).run()
    except KeyboardInterrupt:
        pass
    finally:
        stats_file.write_text(json.dumps({
            "locks": locks,
            "valio_per_call": valio["per_call"],
            "budgets": [{"calls": b.calls, "ids": b.ids_sent, "per_call": b.per_call}
                        for b in valio["budgets"] if b.calls],
            "db_locked": valio["db_locked"],
        }))


# ---------------------------------------------------------------- client side

def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(p / 100 * (len(xs) - 1)))]


async def agent(i: int, rounds: int, lines: list, http, holder_for, lat: dict, errors: list) -> int:
    holder = None
    done = 0

    async def timed(route: str, method: str, url: str, **kw):
        t = time.perf_counter()
        r = await http.request(method, url, **kw)
        lat[route].append(time.perf_counter() - t)
        if r.is_error:
            errors.append((route, r.status_code, r.text[:120]))
            return None
        return r.json()

    async def auth():
        n = await timed("GET /agent/v1/nonce", "GET", "/agent/v1/nonce")
        return {"Authorization": f"SD-JWT {holder.present(n['nonce'], n.get('iat'))}"}

    for k in range(rounds):
        holder = holder_for()  # a pass per round: its per week limit counts every order placed under it
        req = await timed("POST /agent/v1/requests", "POST", "/agent/v1/requests", headers=await auth(), json={
            "lines": lines, "deliverBy": "2026-11-16", "idempotencyKey": f"load-{i}-{k}"})
        if not req or req["decision"]["outcome"] != "auto_order":
            continue
        choice = [{"productId": ln["chosen"]["productId"], "salesQty": ln["chosen"]["salesQty"]}
                  for ln in req["lines"] if ln.get("chosen")]
        order = await timed("POST /agent/v1/orders", "POST", "/agent/v1/orders", headers=await auth(), json={
            "requestId": req["id"], "choice": choice, "idempotencyKey": f"load-{i}-{k}-order"})
        if not order:
            continue
        got = await timed("GET /agent/v1/orders/{id}", "GET", f"/agent/v1/orders/{order['id']}")
        done += bool(got and got["state"] == "placed")
    return done


class Presenter:
    """A Holder whose nonce is passed in, so the async client can fetch it itself."""

    def __init__(self, issuance, key):
        from validio.agent.holder import DISCLOSE
        from validio.policy.mandate import AUDIENCE, present
        self.issuance, self.key, self._present, self._aud, self._disclose = issuance, key, present, AUDIENCE, DISCLOSE

    def present(self, nonce: str, iat: int | None = None) -> str:
        """Signed on Validio's clock (`iat` from the nonce answer), as the server checks it."""
        return self._present(self.issuance, self._disclose, self.key, self._aud, nonce, iat)


def run_level(n: int, rounds: int, mix: str = "scene2") -> dict:
    import httpx

    tmp = Path(tempfile.mkdtemp(prefix=f"validio-load-{n}-"))
    env = {**os.environ, "VALIDIO_DB": str(tmp / "validio.db"), "VALIDIO_KEYS": str(tmp / "keys"),
           "VALIO_MODE": "replay"}
    subprocess.run([sys.executable, "-c", "from validio.demo import seed; seed.reset()"], env=env, check=True,
                   cwd=ROOT / "src" / "backend")
    port, stats_file = free_port(), tmp / "server-stats.json"
    proc = subprocess.Popen([sys.executable, __file__, "--serve", str(port), str(stats_file)], env=env,
                            cwd=ROOT / "src" / "backend")
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(200):
            try:
                if httpx.get(f"{base}/api/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.05)
        os.environ["VALIDIO_DB"], os.environ["VALIDIO_KEYS"] = env["VALIDIO_DB"], env["VALIDIO_KEYS"]
        from itertools import count

        from validio.agent.holder import Holder
        from validio.demo.seed import load_or_create_key
        from validio.policy.mandate import DEMO_CLAIMS, DEMO_SD_FIELDS, issue_mandate

        seq, kitchen = count(1), load_or_create_key(tmp / "keys" / "kitchen-es256.json")

        def holder_for():  # its own pass per agent round, M-1's limits, signed by the same kitchen key
            h = Holder.from_seed(lambda: "", tmp / "validio.db", tmp / "keys")
            claims = {**DEMO_CLAIMS, "jti": f"L-{next(seq)}"}
            return Presenter(issue_mandate(claims, DEMO_SD_FIELDS, kitchen, h.key), h.key)

        lat: dict = defaultdict(list)
        errors: list = []

        async def load():
            limits = httpx.Limits(max_connections=n + 5, max_keepalive_connections=n + 5)
            async with httpx.AsyncClient(base_url=base, timeout=120, limits=limits) as http:
                return await asyncio.gather(*(agent(i, rounds, MIXES[mix], http, holder_for, lat, errors)
                                              for i in range(n)))

        t0 = time.perf_counter()
        placed = asyncio.run(load())
        wall = time.perf_counter() - t0
    finally:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=30)
    server = json.loads(stats_file.read_text())
    total = sum(len(v) for v in lat.values())
    return {"agents": n, "rounds": rounds, "mix": mix, "wall_s": wall, "http_requests": total, "placed": sum(placed),
            "scenes": n * rounds, "errors": len(errors), "error_samples": errors[:5],
            "routes": {r: {"n": len(v), "p50_ms": 1000 * pct(v, 50), "p95_ms": 1000 * pct(v, 95),
                           "max_ms": 1000 * max(v)} for r, v in lat.items()},
            "server": server}


def machine() -> str:
    cpu = next((ln.split(":", 1)[1].strip() for ln in Path("/proc/cpuinfo").read_text().splitlines()
                if ln.startswith("model name")), platform.processor())
    mem = next((int(ln.split()[1]) // 1024 // 1024 for ln in Path("/proc/meminfo").read_text().splitlines()
                if ln.startswith("MemTotal")), 0)
    return (f"{cpu}, {os.cpu_count()} logical CPUs, {mem} GiB RAM, {platform.system()} {platform.release()}, "
            f"Python {platform.python_version()}")


def report(res: dict) -> str:
    s = res["server"]
    calls = [b["calls"] for b in s["budgets"]]
    ids = [b["ids"] for b in s["budgets"]]
    per_call = [c[1] for c in s["valio_per_call"]]
    head = (f"N={res['agents']} ({res['mix']}): {res['scenes']} scenes, {res['placed']} orders placed, "
            f"{res['http_requests']} HTTP requests in {res['wall_s']:.2f} s = "
            f"{res['http_requests'] / res['wall_s']:.1f} req/s, "
            f"{res['scenes'] / res['wall_s']:.2f} scenes/s, {res['errors']} errors "
            f"({100 * res['errors'] / max(1, res['http_requests']):.1f} %)")
    out = [head]
    for r, v in sorted(res["routes"].items()):
        out.append(f"  {r:<28} n={v['n']:<5} p50 {v['p50_ms']:8.1f} ms  p95 {v['p95_ms']:8.1f} ms  "
                   f"max {v['max_ms']:8.1f} ms")
    for name, lk in sorted(s["locks"].items()):
        out.append(f"  lock {name:<24} {lk['acquired']} acquired, {lk['waits']} waited, {lk['wait_s']:.3f} s "
                   f"in total, longest {1000 * lk['max_wait_s']:.1f} ms")
    out.append(f"  sqlite 'database is locked': {s['db_locked']}")
    if per_call:
        out.append(f"  Valio: {len(per_call)} calls, ids per call max {max(per_call)} (Valio allows 1000), "
                   f"{len(calls)} checks with calls, calls per check {min(calls)} to {max(calls)}, "
                   f"distinct ids per check max {max(ids)} (cap 40)")
    return "\n".join(out)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        serve(int(sys.argv[2]), Path(sys.argv[3]))
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", type=int, nargs="+", default=[1, 10, 50])
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--mix", choices=sorted(MIXES), default="scene2")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    print(f"machine: {machine()}\ncommand: {' '.join(sys.argv)}\n", flush=True)
    results = []
    for n in a.agents:
        res = run_level(n, a.rounds, a.mix)
        results.append(res)
        print(report(res) + "\n", flush=True)
    if a.json:
        a.json.write_text(json.dumps({"machine": machine(), "results": results}, indent=1))


if __name__ == "__main__":
    main()
