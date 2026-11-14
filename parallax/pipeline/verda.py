"""Verda GPU instance for the bge-m3 embedding job (PLAN A6, side quest c-56), via the Verda Public API.

Credentials come from parallax/.env (VERDA_CLIENT_ID, VERDA_CLIENT_SECRET) and are never printed.
  python -m pipeline.verda types            GPU types with on-demand and spot price and where they are available
  python -m pipeline.verda create TYPE      spot instance with ~/.ssh/id_ed25519.pub, Ubuntu + CUDA image
  python -m pipeline.verda status           our instances, status and IP
  python -m pipeline.verda delete           delete every instance this script created (hostname parallax-embed*)
Every create and delete is appended to data/verda.jsonl (times, type, price) for docs/VERDA.md.
"""

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from contract.db import load_env
from pipeline.fetch import DATA

API = "https://api.verda.com/v1"
HOST = "parallax-embed"
LOG = DATA / "verda.jsonl"


def token() -> dict:
    load_env()
    r = requests.post(
        f"{API}/oauth2/token",
        json={
            "grant_type": "client_credentials",
            "client_id": os.environ["VERDA_CLIENT_ID"],
            "client_secret": os.environ["VERDA_CLIENT_SECRET"],
        },
        timeout=30,
    )
    if r.status_code != 200:
        sys.exit(f"Verda token request failed with HTTP {r.status_code}")
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def call(method: str, path: str, h: dict, **kw):
    r = requests.request(method, f"{API}{path}", headers=h, timeout=60, **kw)
    if r.status_code >= 400:
        sys.exit(f"Verda {method} {path}: HTTP {r.status_code} {r.text[:300]}")
    return r.json() if r.content and "json" in r.headers.get("content-type", "") else r.text


def log(event: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.now(UTC).isoformat(timespec="seconds"), **event}) + "\n")


def types(h: dict) -> None:
    av: dict[str, list[str]] = {}
    for spot in ("false", "true"):
        for loc in call("GET", "/instance-availability", h, params={"is_spot": spot}):
            for t in loc.get("availabilities", []):
                av.setdefault(t, []).append(loc["location_code"] + ("/spot" if spot == "true" else ""))
    for t in sorted(call("GET", "/instance-types", h), key=lambda x: float(x.get("price_per_hour") or 0)):
        if (t.get("gpu") or {}).get("number_of_gpus") and t["instance_type"] in av:
            print(
                f"{t['instance_type']:20} {t['gpu']['description'][:26]:26} {t['price_per_hour']}/h "
                f"spot {t.get('spot_price')}/h  {av[t['instance_type']]}"
            )


def ssh_key_id(h: dict) -> str:
    pub = (Path.home() / ".ssh" / "id_ed25519.pub").read_text().strip()
    body = " ".join(pub.split()[:2])
    for k in call("GET", "/ssh-keys", h):
        if " ".join(str(k.get("key", "")).split()[:2]) == body:
            return k["id"]
    return call("POST", "/ssh-keys", h, json={"name": "parallax-laptop", "key": pub})


def image(h: dict) -> str:
    imgs = [
        i
        for i in call("GET", "/images", h)
        if "cuda" in i["image_type"]
        and "kubernetes" not in i["image_type"]
        and not i["image_type"].endswith((".cc", ".docker"))
    ]
    return sorted(imgs, key=lambda i: i["image_type"], reverse=True)[0]["image_type"]


def create(h: dict, itype: str, location: str) -> None:
    price = next(t for t in call("GET", "/instance-types", h) if t["instance_type"] == itype)
    body = {
        "instance_type": itype,
        "image": image(h),
        "ssh_key_ids": [ssh_key_id(h)],
        "hostname": HOST,
        "description": "Parallax bge-m3 embedding (Junction 2026)",
        "location_code": location,
        "is_spot": True,
        "os_volume": {"name": f"{HOST}-os", "size": 100},
    }
    iid = call("POST", "/instances", h, json=body)
    iid = iid.strip('"') if isinstance(iid, str) else iid
    log(
        {
            "event": "create",
            "id": iid,
            "type": itype,
            "image": body["image"],
            "location": location,
            "spot": True,
            "spot_price": price.get("spot_price"),
        }
    )
    print(f"created {iid} ({itype}, spot {price.get('spot_price')} EUR/h, image {body['image']})")
    for _ in range(90):
        inst = call("GET", f"/instances/{iid}", h)
        print(f"  status={inst.get('status')} ip={inst.get('ip')}", flush=True)
        if inst.get("status") == "running" and inst.get("ip"):
            log({"event": "running", "id": iid, "ip_set": True})
            print(f"READY {inst['ip']}")
            return
        time.sleep(10)
    print("not running after 15 minutes; check `status`")


def ours(h: dict) -> list[dict]:
    return [i for i in call("GET", "/instances", h) if str(i.get("hostname", "")).startswith(HOST)]


def status(h: dict) -> None:
    for i in ours(h):
        print(i["id"], i.get("instance_type"), i.get("status"), i.get("ip"), i.get("created_at"))
    print("balance", call("GET", "/balance", h))


def delete(h: dict) -> None:
    ids = [i["id"] for i in ours(h) if i.get("status") not in ("deleting", "deleted")]
    if not ids:
        print("no parallax instances")
        return
    call("PUT", "/instances", h, json={"action": "delete", "id": ids, "delete_permanently": True})
    log({"event": "delete", "ids": ids})
    print(f"deleted {ids}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["types", "create", "status", "delete"])
    ap.add_argument("type", nargs="?", default="1A100.22V")
    ap.add_argument("--location", default="FIN-01")
    a = ap.parse_args()
    hdr = token()
    {
        "types": lambda: types(hdr),
        "create": lambda: create(hdr, a.type, a.location),
        "status": lambda: status(hdr),
        "delete": lambda: delete(hdr),
    }[a.cmd]()
