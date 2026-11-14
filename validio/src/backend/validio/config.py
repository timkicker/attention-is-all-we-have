"""Settings from the environment and validio/.env. Secrets live only in .env (gitignored)."""

import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # the validio/ folder
DATA = ROOT / "data"
DEFAULT_ENV = ROOT / ".env"


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip() if not line.lstrip().startswith("#") else ""
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


@dataclass(frozen=True)
class Settings:
    valio_base_url: str
    valio_api_key: str = field(repr=False)  # never in a log line
    valio_mode: str
    valio_max_ids: int
    valio_customer: str
    now: datetime
    # VALIDIO_REAL_TIME=1: what happens is stamped with the real time (ledger, orders, requests, the agent link);
    # the decisions keep `now`, which Valio's replayed cut-offs and delivery dates and the pass's week fit
    real_time: bool
    demo: bool
    catalog_db: Path
    valio_cache: Path


def load_settings(env_file: Path | None = DEFAULT_ENV) -> Settings:
    env = _read_env_file(env_file) if env_file else {}
    env.update({k: v for k, v in os.environ.items()})

    def get(k: str, default: str) -> str:
        return env.get(k) or default

    mode = get("VALIO_MODE", "replay")
    if mode not in ("live", "record", "replay"):
        raise ValueError(f"VALIO_MODE must be live, record or replay, not {mode!r}")
    return Settings(
        valio_base_url=get("VALIO_BASE_URL", "https://junction26.valioaimo.fi"),
        valio_api_key=get("VALIO_API_KEY", ""),
        valio_mode=mode,
        valio_max_ids=int(get("VALIO_MAX_IDS_PER_REQUEST", "40")),
        valio_customer=get("VALIO_CUSTOMER", "hotel-espoo"),
        now=datetime.fromisoformat(get("VALIDIO_NOW", "2026-11-14T10:00:00+02:00")),
        real_time=get("VALIDIO_REAL_TIME", "0") == "1",
        demo=get("VALIDIO_DEMO", "0") == "1",  # the demo switches are off unless asked for
        catalog_db=Path(get("VALIDIO_CATALOG_DB", str(DATA / "catalog.db"))),
        valio_cache=Path(get("VALIDIO_VALIO_CACHE", str(DATA / "cache" / "valio"))),
    )


@cache
def _env_file_value(path: Path, key: str) -> str | None:
    return _read_env_file(path).get(key)


_STRICT_STOCK: ContextVar[bool] = ContextVar("strict_placeholder_stock", default=False)


@contextmanager
def strict_stock(on: bool):
    """Within it, placeholder stock is no real count whatever STRICT_PLACEHOLDER_STOCK says: a kitchen's own
    account decides with real money, so it never orders automatically on a count nobody made. It only turns strict on."""
    token = _STRICT_STOCK.set(_STRICT_STOCK.get() or on)
    try:
        yield
    finally:
        _STRICT_STOCK.reset(token)


def strict_placeholder_stock() -> bool:
    """STRICT_PLACEHOLDER_STOCK=1: Valio's placeholder stock numbers (9999999999, 666666666) count as no real
    count, so nothing orders automatically on them. Off by default for the demo and the local kitchen until a Valio
    mentor says what they mean; always on for a kitchen's own account (`strict_stock`)."""
    if _STRICT_STOCK.get():
        return True
    v = os.environ.get("STRICT_PLACEHOLDER_STOCK")
    if v is None:
        v = _env_file_value(DEFAULT_ENV, "STRICT_PLACEHOLDER_STOCK")
    return v == "1"
