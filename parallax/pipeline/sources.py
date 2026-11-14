"""A14: what each edition cites, through time: <ref> count, ISBN registration groups and URL domains per snapshot,
loaded into ref_stat as lives (each snapshot holds until the next one)."""

import argparse
import json
import re
from collections import Counter

from contract.db import connect
from pipeline import stat
from pipeline.fetch import hist_dir
from pipeline.lives import fmt, parse_ts
from pipeline.load import versioned
from pipeline.parse import revisions

REF = re.compile(r"<ref\b", re.I)
ISBN = re.compile(r"isbn\s*(?:=|:|\|)?\s*((?:97[89][\s\-‐–]?)?[0-9][0-9\s\-‐–]{7,15}[0-9Xx])", re.I)
URL = re.compile(r"https?://([^/\s|\]\}<>\"']+)", re.I)
GROUPS = [
    ("9985", "EE"),
    ("9949", "EE"),
    ("966", "UA"),
    ("617", "UA"),
    ("951", "FI"),
    ("952", "FI"),
    ("985", "BY"),
    ("91", "SE"),
    ("82", "NO"),
    ("87", "DK"),
    ("90", "NL"),
    ("94", "NL"),
    ("83", "PL"),
    ("10", "FR"),
    ("2", "FR"),
    ("3", "DE"),
    ("5", "RU/USSR"),
    ("0", "EN"),
    ("1", "EN"),
]


def isbn_group(raw: str) -> str | None:
    digits = re.sub(r"[^0-9Xx]", "", raw).upper()
    if len(digits) == 13 and digits[:3] in ("978", "979"):
        body = digits[3:]
        if digits[:3] == "979" and body.startswith("10"):
            return "FR"
    elif len(digits) == 10:
        body = digits
    else:
        return None
    for prefix, group in GROUPS:
        if body.startswith(prefix):
            return group
    return "other"


def ref_counts(text: str) -> dict:
    isbn = Counter()
    seen = set()
    for m in ISBN.finditer(text):
        key = re.sub(r"[^0-9X]", "", m.group(1).upper())
        if key in seen:
            continue
        seen.add(key)
        g = isbn_group(m.group(1))
        if g:
            isbn[g] += 1
    domains = Counter()
    for m in URL.finditer(text):
        d = m.group(1).lower().split(":")[0]
        d = d[4:] if d.startswith("www.") else d
        if "wikipedia.org" in d or "wikimedia.org" in d:
            continue
        domains[d] += 1
    return {"refs": len(REF.findall(text)), "isbn": dict(isbn.most_common()), "domains": dict(domains.most_common(30))}


def yearly(revs: list[dict]) -> list[dict]:
    """The revision current at each 1 January plus the latest one (fi has every revision)."""
    out, i = [], 0
    if not revs:
        return out
    for year in range(int(revs[0]["ts"][:4]) + 1, int(revs[-1]["ts"][:4]) + 1):
        cut = f"{year}-01-01T00:00:00Z"
        while i + 1 < len(revs) and revs[i + 1]["ts"] < cut:
            i += 1
        if revs[i]["ts"] < cut and (not out or out[-1]["rev_id"] != revs[i]["rev_id"]):
            out.append(revs[i])
    if not out or out[-1]["rev_id"] != revs[-1]["rev_id"]:
        out.append(revs[-1])
    return out


def run(topic_id: str) -> None:
    pages = json.loads((hist_dir(topic_id) / "pages.json").read_text(encoding="utf-8"))
    cur = connect().cursor()
    cur.execute("SET system_versioning_insert_history=1")
    rows, current = [], {}
    for lang in pages:
        snaps = yearly(revisions(topic_id, lang))
        for k, r in enumerate(snaps):
            c = ref_counts(r["text"])
            end = fmt(parse_ts(snaps[k + 1]["ts"])) if k + 1 < len(snaps) else None
            rows.append(
                {
                    "topic_id": topic_id,
                    "lang": lang,
                    "rev_id": r["rev_id"],
                    "refs": c["refs"],
                    "isbn": json.dumps(c["isbn"]),
                    "domains": json.dumps(c["domains"], ensure_ascii=False),
                    "row_start": fmt(parse_ts(r["ts"])),
                    "row_end": end,
                }
            )
            if end is None:
                current[lang] = c
    cur.execute("SELECT COUNT(*) FROM ref_stat FOR SYSTEM_TIME ALL WHERE topic_id=%s", (topic_id,))
    if cur.fetchone()[0]:
        raise SystemExit("ref_stat already has this topic; run `make load` first (DELETE keeps history)")
    n = versioned(cur, "ref_stat", ["topic_id", "lang", "rev_id", "refs", "isbn", "domains"], rows)
    summary = {}
    for lang, c in current.items():
        total = sum(c["isbn"].values())
        own = {"fi": "FI", "sv": "SE", "de": "DE", "ru": "RU/USSR", "et": "EE", "uk": "UA", "en": "EN"}[lang]
        summary[lang] = {
            "refs": c["refs"],
            "isbn": total,
            "own_group_share": round(c["isbn"].get(own, 0) / total, 3) if total else None,
            "top_isbn": c["isbn"],
            "top_domains": list(c["domains"])[:5],
        }
        print(f"{lang}: refs={c['refs']:4} isbn={total:3} {c['isbn']} domains={list(c['domains'])[:3]}")
    stat.put(cur, "sources", {"rows": n, "current": summary})
    fi = summary.get("fi", {})
    print(
        f"rows={n}; fi FI share among ISBNs = {fi.get('own_group_share')}; most refs: "
        f"{max(summary, key=lambda x: summary[x]['refs'])}"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    run(ap.parse_args().topic)
