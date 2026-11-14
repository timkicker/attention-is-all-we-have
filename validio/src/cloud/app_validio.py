"""Validio itself on Modal: the FastAPI app and the built web app on one public link, in replay mode.

Aiven is not used tonight, so the plan's fallback holds: one container at most, scaling to zero, SQLite on
the Modal Volume `validio-data` and a volume commit after every write. The catalog index and the recorded
Valio answers sit in the same volume, never in the image or in git. The app's own gate does the rest:
VALIDIO_PUBLIC=1 makes it refuse to start without the 6 digit approve code, the kitchen token and the demo
token, all from the Modal secret `validio-web` (VALIDIO_PUBLIC, VALIDIO_DEMO, VALIDIO_APPROVE_CODE,
VALIDIO_KITCHEN_TOKEN, VALIDIO_DEMO_TOKEN, VALIDIO_MCP_HOSTS), never in git.

Run from validio/:
  make modal-data      upload data/catalog.db and data/cache/valio to the volume (once, or after make record)
  make modal-secret    create the secret from MODAL_SECRETS (a 600 file, written with fresh values if missing)
  make modal-deploy    build the web app, deploy, then reset the demo state in the volume
  make modal-seed      reset the demo state in the volume again
Stop:  modal app stop validio-web
"""

import tomllib
from pathlib import Path

import modal

REMOTE = "/app"  # validio/ inside the container, so config.ROOT and DATA resolve the same way
DATA = f"{REMOTE}/data"
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
