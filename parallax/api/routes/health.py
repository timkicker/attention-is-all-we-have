import os

from fastapi import APIRouter

from api import sqllog
from contract.engine import get_engine

router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    sqllog.panel("health")
    try:
        (counts,) = sqllog.run_file("health")
        db = "ok"
    except Exception as e:  # the health check reports instead of failing
        counts, db = {"claim": 0, "claim_life_fi": 0, "verdict": 0, "seed": None}, f"error: {type(e).__name__}"
    # The seed the database was loaded from (scripts/load_sql.py), else the one .env names.
    seed = counts.pop("seed") or os.environ.get("SEED", "unknown")
    engine = get_engine()
    return {
        "db": db,
        "engine": engine.name,
        "model_id": engine.model_id,
        "seed": seed,
        "counts": {k: int(v) for k, v in counts.items()},
    }
