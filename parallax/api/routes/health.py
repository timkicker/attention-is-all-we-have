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
        counts, db = {"claim": 0, "claim_life_fi": 0, "verdict": 0}, f"error: {type(e).__name__}"
    engine = get_engine()
    return {
        "db": db,
        "engine": engine.name,
        "model_id": engine.model_id,
        "seed": os.environ.get("SEED", "unknown"),
        "counts": {k: int(v) for k, v in counts.items()},
    }
