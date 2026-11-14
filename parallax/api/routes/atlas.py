"""Atlas: every topic in fi, sv or en with the cosine distance between the article vectors of two editions."""

from typing import Literal

from fastapi import APIRouter, Query

from api import sqllog

router = APIRouter()
COVERAGES = ("all", "fi+sv", "fi+en", "fi")
# Sort keys map to fixed SQL; NULL distances (edition missing) always last.
ORDER = {
    "wikidata_id": "CAST(SUBSTRING(wikidata_id, 2) AS UNSIGNED)",
    "fi_sv": "dist_fi_sv IS NULL, dist_fi_sv DESC",
    "fi_en": "dist_fi_en IS NULL, dist_fi_en DESC",
    "sv_en": "dist_sv_en IS NULL, dist_sv_en DESC",
}


@router.get("/api/atlas")
def atlas(
    coverage: Literal["fi", "fi+sv", "fi+en", "all"] | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    sort: Literal["wikidata_id", "fi_sv", "fi_en", "sv_en"] = "wikidata_id",
) -> dict:
    sqllog.panel("atlas")
    counts = {c: 0 for c in COVERAGES} | {r["coverage"]: int(r["n"]) for r in sqllog.run_file("atlas_counts")}
    rows = sqllog.run(
        sqllog.query("atlas").replace("{order}", ORDER[sort]),
        {"coverage": coverage, "limit": limit, "offset": offset},
    )
    return {
        "counts": counts,
        "topics": [
            {
                "wikidata_id": r["wikidata_id"],
                "titles": {lang: r[f"title_{lang}"] for lang in ("fi", "sv", "en")},
                "coverage": r["coverage"],
                "dist": {
                    k: None if r[f"dist_{k}"] is None else round(float(r[f"dist_{k}"]), 4)
                    for k in ("fi_sv", "fi_en", "sv_en")
                },
                "topic_id": r["topic_id"],
            }
            for r in rows
        ],
    }
