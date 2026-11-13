"""The backend for the live Playwright run (playwright.scenes.config.ts).

Starts the real backend the way scripts/demo_check.py does (replayed Valio answers, no network,
a fresh store under artifacts/web-live), with the approval code and the demo token SET, so the
pages have to send both. Then it plays scenes 1 and 2 and the agent's half of scene 3 (stock-out,
the request that waits), and leaves the owner's approval to the browser. Runs until stopped.

    cd validio/src/backend && uv run python ../frontend/e2e/live/serve.py
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from demo_check import Run, env, start_server  # noqa: E402

PORT = int(os.environ.get("LIVE_PORT", "8433"))
CODE = os.environ.get("LIVE_CODE", "135790")
TOKEN = os.environ.get("LIVE_TOKEN", "live-run-token")


async def fill(base: str, db: Path) -> None:
    keys = Path(env().get("VALIDIO_KEYS") or ROOT / "data" / "keys")
    run = Run(base, db, keys, TOKEN, CODE, False)
    run.demo("reset")
    await run.agent(1)
    await run.agent(2)
    run.demo("stock-out")
    await run.agent(3)
    print("filled: R-1 ordered alone, R-2 waiting for the owner", flush=True)


def main() -> int:
    store = ROOT / "artifacts" / "web-live"
    store.mkdir(parents=True, exist_ok=True)
    (store / "validio.db").unlink(missing_ok=True)
    proc = start_server(PORT, store, TOKEN, CODE)
    try:
        asyncio.run(fill(f"http://127.0.0.1:{PORT}", store / "validio.db"))
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        proc.wait()
    finally:
        proc.terminate()
        proc.wait(10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
