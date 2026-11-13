"""Put the three Valio files into data/raw/ and check their sha256.

Valio allows the data only for this challenge, so it never goes into git.
--from-dir copies local files, otherwise they are downloaded from the test API with the key in .env.
"""

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
from validio.config import DATA, load_settings
from validio.valio.client import checked_base_url

FILES = {
    "valio_aimo_junction26_product_data.json": (
        "/api/products/download", "50651aae31ca842112afdc16fcce92f9858d7f5d05e9928a3748aef16b22ea02"),
    "valio_aimo_junction26_delivery_reliability.csv": (
        "/api/delivery-reliability/download", "d24dc9e17d2652e7c21ea39fcf08e55522d044313031af1d9f3424fb84b2bb72"),
    "valio_aimo_junction26_carbon_footprint.csv": (
        "/api/carbon-footprint/download", "72b1ed6a22a0a40dcb7969d0c1f21229cdb5b64b5dba68b7db7fc7e947376eac"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-dir", type=Path)
    ap.add_argument("--out", type=Path, default=DATA / "raw")
    args = ap.parse_args()
    base = None if args.from_dir else checked_base_url(load_settings().valio_base_url)
    args.out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for name, (route, want) in FILES.items():
        dst = args.out / name
        if args.from_dir:
            shutil.copyfile(args.from_dir / name, dst)
        else:
            import httpx

            s = load_settings()
            with httpx.stream("GET", base + route, headers={"X-API-Key": s.valio_api_key},
                              timeout=120) as r:
                r.raise_for_status()
                with dst.open("wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
        got = sha256(dst)
        ok = got == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {name} {got[:16]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
