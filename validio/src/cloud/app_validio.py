"""Validio itself on Modal: the FastAPI app and the built web app on one public link, in replay mode.

Aiven is not used tonight, so the plan's fallback holds: one container at most, scaling to zero, SQLite on
the Modal Volume `validio-data` and a volume commit after every write. The catalog index and the recorded
Valio answers sit in the same volume, never in the image or in git. The app's own gate does the rest:
VALIDIO_PUBLIC=1 makes it refuse to start without the 6 digit approve code, the kitchen token and the demo
token, all from the Modal secret `validio-web` (VALIDIO_PUBLIC, VALIDIO_DEMO, VALIDIO_APPROVE_CODE,
VALIDIO_KITCHEN_TOKEN, VALIDIO_MCP_HOSTS, VALIDIO_PUBLIC_READ), never in git.
VALIDIO_PUBLIC_READ=1 lets a visitor read without the kitchen token; every write stays behind the gates.

Run from validio/:
  make modal-data      upload data/catalog.db and data/cache/valio to the volume (once, or after make record)
  make modal-secret    create the secret from MODAL_SECRETS (a 600 file, written with fresh values if missing)
  make modal-deploy    build the web app, deploy, then reset the demo state in the volume
  make modal-seed      reset the demo state in the volume again
  make modal-fill      play the five demo scenes into data/template in the volume: the filled demo kitchen every
                       account is copied from (db and keys); the approval codes live in accounts.db
Stop:  modal app stop validio-web
"""

import tomllib
from pathlib import Path

import modal

REMOTE = "/app"  # validio/ inside the container, so config.ROOT and DATA resolve the same way
DATA = f"{REMOTE}/data"
TEMPLATE_DB = f"{DATA}/template/validio.db"  # the filled demo kitchen; each demo copy starts as a copy of it
TEMPLATE_KEYS = f"{DATA}/template/keys"
# Laptop paths exist only where the app is deployed from. Inside the container Modal places this file at
# /root/app_validio.py, so nothing below may look at them there.
LOCAL = modal.is_local()
ROOT = Path(__file__).resolve().parents[2] if LOCAL else None  # validio/


def _deps() -> list[str]:
    # the pinned runtime dependencies of src/backend/pyproject.toml
    if ROOT is None:
        return []
    return tomllib.loads((ROOT / "src" / "backend" / "pyproject.toml").read_text())["project"]["dependencies"]


image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(*_deps())
    .env({
        "PYTHONPATH": f"{REMOTE}/src/backend",
        "VALIO_MODE": "replay",
        "VALIDIO_DEMO": "1",
        "VALIDIO_NOW": "2026-11-14T10:00:00+02:00",
        "VALIDIO_REAL_TIME": "1",  # what jurors do is stamped with the real time, the story keeps VALIDIO_NOW
        "VALIDIO_DB": f"{DATA}/validio.db",
        "VALIDIO_KEYS": f"{DATA}/keys",
        "VALIDIO_CATALOG_DB": f"{DATA}/catalog.db",
        "VALIDIO_VALIO_CACHE": f"{DATA}/cache/valio",
    })
)
if LOCAL:  # the files ride along at deploy time; in the container they are already in place
    image = (
        image.add_local_dir(ROOT / "src" / "backend" / "validio", f"{REMOTE}/src/backend/validio",
                            ignore=["**/__pycache__", "**/*.pyc"])
        .add_local_dir(ROOT / "src" / "frontend" / "build", f"{REMOTE}/src/frontend/build")
        .add_local_file(ROOT / "scripts" / "demo_check.py", f"{REMOTE}/scripts/demo_check.py")
    )

data = modal.Volume.from_name("validio-data", create_if_missing=True)
web_secret = modal.Secret.from_name("validio-web")
app = modal.App("validio-web")


@app.function(image=image, volumes={DATA: data}, secrets=[web_secret], min_containers=0, max_containers=1,
              scaledown_window=300, timeout=600)
@modal.concurrent(max_inputs=32)
@modal.asgi_app(label="validio")
def web():
    from fastapi import Request

    from validio.api.app import app as api  # serves the built web app too, and refuses to start open

    @api.middleware("http")
    async def commit_after_writes(request: Request, call_next):
        response = await call_next(request)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            await data.commit.aio()  # the next container must see every order and ledger entry
        return response

    return api


@app.function(image=image, volumes={DATA: data}, timeout=300)
def seed() -> str:
    """The same state as `make seed`, in the volume."""
    from validio.demo import seed as demo_seed

    path = demo_seed.reset()
    data.commit()
    return f"seeded {path}"


@app.function(image=image, volumes={DATA: data}, timeout=600)
def fill() -> str:
    """demo_check's five scenes, one round from a reset, against the template in the volume: the app runs in
    this container on 127.0.0.1 (no public gate here, no secret) with the template as its store, the scenes go
    through its API and MCP, then the demo Rules are saved (--template), the agent is left unconnected and the
    volume is committed. Every account is copied from this template. Run it while no web container is up, so
    none holds an older copy."""
    import os
    import secrets
    import subprocess
    import sys

    from validio.api import connect
    from validio.demo import seed as demo_seed

    demo_seed.reset(Path(TEMPLATE_DB), Path(TEMPLATE_KEYS))
    port = "8419"
    # a throwaway code that lives only in this container, so the scenes check the gate too
    env = {**os.environ, "VALIDIO_PUBLIC": "", "VALIDIO_KITCHEN_TOKEN": "", "VALIDIO_REAL_TIME": "",
           "VALIDIO_DB": TEMPLATE_DB, "VALIDIO_KEYS": TEMPLATE_KEYS,
           "VALIDIO_APPROVE_CODE": f"{secrets.randbelow(10**6):06d}"}
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "validio.api.app:app", "--host", "127.0.0.1",
                               "--port", port], cwd=f"{REMOTE}/src/backend", env=env)
    try:
        import time

        import httpx

        for _ in range(150):
            try:
                if httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        run = subprocess.run([sys.executable, f"{REMOTE}/scripts/demo_check.py", "--base", f"http://127.0.0.1:{port}",
                              "--rounds", "1", "--template"], env=env, capture_output=True, text=True, timeout=500, check=False)
    finally:
        server.terminate()
        server.wait(10)
    out = run.stdout + run.stderr
    if run.returncode != 0 or "ALL SCENES OK" not in out:
        raise RuntimeError(f"demo scenes failed, volume not committed:\n{out[-3000:]}")
    connect.leave_unconnected(Path(TEMPLATE_DB))  # a juror connects the demo agent first
    data.commit()
    return out
