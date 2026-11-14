"""A2: raw history of one topic on disk.

Non-fi editions: full revision metadata from the API plus the wikitext of yearly snapshots.
fi: every revision of the page from the M dataset (never the user or anonymous columns).
Output in data/hist/<topic>/.
"""

import argparse
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from pipeline import wapi

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
M_COLUMNS = ["page_id", "title", "rev_id", "parent_id", "timestamp", "comment", "minor", "sha1", "bytes", "text"]


def topics() -> dict:
    return yaml.safe_load((ROOT / "pipeline" / "topics.yaml").read_text(encoding="utf-8"))


def hist_dir(topic: str) -> Path:
    return DATA / "hist" / topic


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    n = 0
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    tmp.replace(path)
    return n


def read_jsonl(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def meta_row(rev: dict) -> dict:
    """One revision's metadata. User names are never requested and never kept."""
    return {
        "rev_id": rev["revid"],
        "parent_id": rev.get("parentid") or None,
        "ts": rev["timestamp"],
        "bytes": rev.get("size"),
        "minor": 1 if rev.get("minor") else 0,
        "sha1": rev.get("sha1"),
        "comment": rev.get("comment"),
    }


def pick_snapshots(meta: list[dict], last_year: int | None = None) -> list[int]:
    """For each 1 January from the year after the first revision to last_year, the revision current at 00:00 UTC,
    plus the current revision. Sorted, without duplicates."""
    if not meta:
        return []
    meta = sorted(meta, key=lambda r: r["ts"])
    last_year = last_year or datetime.now(UTC).year
    first_year = int(meta[0]["ts"][:4])
    picked: list[int] = []
    i = 0
    for year in range(first_year + 1, last_year + 1):
        cut = f"{year}-01-01T00:00:00Z"
        while i + 1 < len(meta) and meta[i + 1]["ts"] < cut:
            i += 1
        if meta[i]["ts"] < cut:
            picked.append(meta[i]["rev_id"])
    picked.append(meta[-1]["rev_id"])
    out: list[int] = []
    for r in picked:
        if r not in out:
            out.append(r)
    return out


def titles(topic: dict) -> dict[str, str]:
    body = wapi.get(
        wapi.api_url("fi"),
        {"action": "query", "prop": "langlinks", "lllimit": "max", "titles": topic["fi_title"], "formatversion": 2},
    )
    page = body["query"]["pages"][0]
    out = {"fi": page["title"]}
    out.update({ll["lang"]: ll["title"] for ll in page.get("langlinks", []) if ll["lang"] in topic["langs"]})
    return out


def fetch_meta(lang: str, title: str) -> tuple[int, list[dict]]:
    page_id = None
    rows: list[dict] = []
    for body in wapi.query_all(
        lang,
        {
            "prop": "revisions",
            "titles": title,
            "rvprop": "ids|timestamp|size|flags|sha1|comment",
            "rvlimit": "max",
            "rvdir": "newer",
        },
    ):
        page = body["query"]["pages"][0]
        page_id = page["pageid"]
        rows.extend(meta_row(r) for r in page.get("revisions", []))
    return page_id, rows


def fetch_texts(lang: str, rev_ids: list[int]) -> list[dict]:
    out = []
    for i in range(0, len(rev_ids), 10):
        chunk = rev_ids[i : i + 10]
        body = wapi.get(
            wapi.api_url(lang),
            {
                "action": "query",
                "prop": "revisions",
                "revids": "|".join(map(str, chunk)),
                "rvprop": "ids|timestamp|comment|sha1|content",
                "rvslots": "main",
                "formatversion": 2,
            },
        )
        for page in body["query"]["pages"]:
            for r in page.get("revisions", []):
                text = r.get("slots", {}).get("main", {}).get("content")
                if text is None:  # hidden revision
                    continue
                out.append(
                    {
                        "rev_id": r["revid"],
                        "ts": r["timestamp"],
                        "comment": r.get("comment"),
                        "sha1": r.get("sha1"),
                        "text": text,
                    }
                )
    return sorted(out, key=lambda r: r["ts"])


def m_page_rows(m_file: Path, page_id: int) -> list[dict]:
    table = pq.read_table(m_file, columns=M_COLUMNS, filters=[("page_id", "=", page_id)])
    table = table.sort_by("timestamp")
    rows = []
    for r in table.to_pylist():
        ts = r["timestamp"]
        rows.append(
            {
                "rev_id": r["rev_id"],
                "parent_id": r["parent_id"],
                "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(ts, "strftime") else str(ts),
                "bytes": r["bytes"],
                "minor": 1 if r["minor"] else 0,
                "sha1": r["sha1"],
                "comment": r["comment"],
                "title": r["title"],
                "text": r["text"],
            }
        )
    return rows


def run(topic_id: str) -> None:
    topic = topics()[topic_id]
    out = hist_dir(topic_id)
    names = titles(topic)
    pages = {}
    table = []
    for lang in topic["langs"]:
        if lang == "fi":
            rows = m_page_rows(DATA / "m" / topic["m_file"], topic["fi_page"])
            write_jsonl(out / "fi.every.jsonl.gz", rows)
            write_jsonl(out / "fi.meta.jsonl.gz", ({k: v for k, v in r.items() if k != "text"} for r in rows))
            pages["fi"] = {"page_id": topic["fi_page"], "title": names["fi"], "source": "M", "history": "every"}
            table.append((lang, len(rows), len(rows)))
            continue
        page_id, meta = fetch_meta(lang, names[lang])
        write_jsonl(out / f"{lang}.meta.jsonl.gz", meta)
        snaps = fetch_texts(lang, pick_snapshots(meta))
        write_jsonl(out / f"{lang}.snap.jsonl.gz", snaps)
        pages[lang] = {"page_id": page_id, "title": names[lang], "source": "api", "history": "yearly"}
        table.append((lang, len(meta), len(snaps)))
    (out / "pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'lang':5} {'revisions':>9} {'texts':>6}")
    for lang, n_meta, n_text in table:
        print(f"{lang:5} {n_meta:9} {n_text:6}")
    print(wapi.stats_line())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    run(ap.parse_args().topic)
