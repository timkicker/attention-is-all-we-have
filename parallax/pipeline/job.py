"""Any-article ingest: the pipeline (fetch, parse, lives, embed, load, align, judge, gloss) as one job per Wikidata
item, run by a worker thread in the API or from the command line (`make ingest QID=...`, `make prepare QIDS=...`).

The topic definition comes from Wikidata, not from topics.yaml: the qid, the English label and the title in each of
the seven editions (sitelinks). The topic id is the lowercase qid (Q155093 -> q155093): stable, unique, fits
VARCHAR(32) and never collides with the hand-made ids such as `winterwar`. An item already in table `topic` (by
wikidata_id) is never ingested again.

Fast path. Editions are done one at a time, Finnish first, then the others from the smallest current article to the
largest, and the next edition's download runs while the current one is parsed and embedded. Each edition gets its
yearly snapshots (the revision current on every 1 January plus the current one; with `since`, only from that date
on), so an edition marked done has its whole history and never changes again. Finnish plus the smallest other edition
is usually loaded within a minute or two: then the job is `usable` and /api/compare?topic=<id> works for it, while the
other editions keep loading.

Model calls are bounded: for every other edition the first JUDGE_CLAIMS Finnish statements in Compare order are judged
against their JUDGE_CANDIDATES nearest statements in that edition, one call per (statement, edition). With
ENGINE=real the matched sentences also get English glosses, 20 per call. The job counts its calls in
ingest_job.model_calls and prints them.
"""

import argparse
import datetime as dt
import logging
import os
import re
import threading
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from contract.db import connect
from contract.engine import Candidate, get_engine, sketch_embed
from pipeline import wapi, wikidata
from pipeline.fetch import fetch_texts, meta_row, pick_snapshots
from pipeline.lives import walk
from pipeline.load import versioned
from pipeline.parse import ParseCache

ROOT = Path(__file__).resolve().parent.parent
LANGS = wikidata.LANGS
JUDGE_CLAIMS = int(os.environ.get("INGEST_JUDGE_CLAIMS") or 25)  # one Compare page
JUDGE_CANDIDATES = 3
GLOSS_BATCH = 20
MAX_TRIES = 3  # per edition, for rate limits
MAX_ACTIVE = int(os.environ.get("INGEST_MAX_ACTIVE") or 3)  # jobs queued or loading at once; more get IngestBusy
MAX_JOB_FAILURES = 3  # a job that crashes the worker this often in a row is marked failed instead of retried forever
log = logging.getLogger("parallax.ingest")

ALIGN_SQL = (ROOT / "pipeline" / "align.sql").read_text(encoding="utf-8")
ALIGN_SQL = "\n".join(line for line in ALIGN_SQL.splitlines() if not line.startswith("--"))
ALIGN_SQL = ALIGN_SQL.replace("INSERT INTO align", "INSERT IGNORE INTO align")
TAIL_SECTIONS = (
    "Lähteet", "Kirjalähteet", "Verkkolähteet", "Kirjallisuutta", "Aiheesta muualla", "Katso myös", "Viitteet",
)  # fmt: skip


class NoFinnish(Exception):
    pass


class UnknownItem(Exception):
    pass


class IngestBusy(Exception):
    """MAX_ACTIVE jobs are queued or loading already; a new one has to wait."""


def topic_slug(qid: str) -> str:
    return qid.lower()


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


# ---------------------------------------------------------------- tables


def ensure_tables(conn=None) -> None:
    """Create ingest_job and ingest_edition from contract/schema.sql when missing. Never drops anything."""
    text = (ROOT / "contract" / "schema.sql").read_text(encoding="utf-8")
    own = conn is None
    conn = conn or connect()
    with conn.cursor() as cur:
        for name in ("ingest_job", "ingest_edition"):
            m = re.search(rf"^CREATE TABLE {name} \(.*?^\);", text, re.S | re.M)
            cur.execute(m.group(0).rstrip(";").replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1))
    if own:
        conn.close()


# ---------------------------------------------------------------- estimates


def estimate_s(en_length: int | None, n_editions: int, since: str | None = None) -> int:
    """Seconds for a whole ingest, before anything is known but the English size and the number of editions.

    Measured on this laptop (Ollama bge-m3 on CPU, about 27 sentences/s): roughly 15 s fixed plus 4 s per edition
    plus 0.4 s per 1,000 bytes of article per edition over its yearly snapshots (Mannerheim Line: 73 s).
    Without an English article 30,000 bytes
    is assumed. `since` (five years) keeps about a third of that."""
    size = en_length or 30_000
    per_edition = 4 + size / 1000 * (0.15 if since else 0.4)
    return int(15 + n_editions * per_edition)


# ---------------------------------------------------------------- create and read (used by the API and the CLI)


def _q(cur, sql: str, params=()) -> list[dict]:
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description] if cur.description else []
    return [dict(zip(cols, r, strict=False)) for r in cur.fetchall()]


def create(cur, qid: str, since: str | None = None, ent: dict | None = None, max_active: int | None = None) -> str:
    """Queue an ingest for qid unless one exists or the item is loaded already. Returns 'existing', 'loaded' or
    'queued'. Raises UnknownItem, NoFinnish, IngestBusy when MAX_ACTIVE jobs are under way (max_active=None: no cap,
    the command line), or wapi.RateLimited when Wikidata cannot be asked now."""
    if _q(cur, "SELECT 1 FROM topic WHERE wikidata_id=%s", (qid,)):
        return "loaded"
    job = _q(cur, "SELECT state, since FROM ingest_job WHERE qid=%s", (qid,))
    if job and job[0]["state"] != "failed":
        old = job[0]["since"]
        if since and job[0]["state"] != "done" and (old is None or dt.date.fromisoformat(since) > old):
            # "Faster" on a running job: editions whose download has not started yet use the later date
            cur.execute("UPDATE ingest_job SET since=%s, updated_at=%s WHERE qid=%s", (since, now(), qid))
            return "narrowed"
        return "existing"
    if max_active is not None:
        (active,) = _q(cur, "SELECT COUNT(*) AS n FROM ingest_job WHERE state IN ('queued','running','usable')")
        if int(active["n"]) >= max_active:
            raise IngestBusy(qid)
    if ent is None:
        if wapi.cooldown_left() > 0:
            raise wapi.RateLimited("cooling down", wapi.cooldown_left())
        ent = wikidata.entity(qid)
    if not ent:
        raise UnknownItem(qid)
    titles = ent["titles"]
    if "fi" not in titles:
        raise NoFinnish(qid)
    title = (titles.get("en") or ent.get("label_en") or titles["fi"])[:255]
    t = now()
    eta = estimate_s(None, len(titles), since)
    cur.execute("DELETE FROM ingest_edition WHERE qid=%s", (qid,))
    cur.execute(
        "REPLACE INTO ingest_job (qid, topic_id, title, state, since, eta_s, created_at, updated_at) "
        "VALUES (%s,%s,%s,'queued',%s,%s,%s,%s)",
        (qid, topic_slug(qid), title, since, eta, t, t),
    )
    cur.executemany(
        "INSERT INTO ingest_edition (qid, lang, title, state, error) VALUES (%s,%s,%s,%s,%s)",
        [
            (qid, lang, titles.get(lang), "waiting" if lang in titles else "failed",
             None if lang in titles else "no_article")
            for lang in LANGS
        ],
    )  # fmt: skip
    return "queued"


def iso(ts: dt.datetime | None) -> str | None:
    return ts.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None


def job_view(job: dict, editions: list[dict]) -> dict:
    """The body of GET /api/ingest/:qid from the job row and its edition rows."""
    by_lang = {e["lang"]: e for e in editions}
    eds = []
    for lang in LANGS:
        e = by_lang.get(lang) or {"state": "failed", "pct": 0, "error": "no_article", "retry_at": None}
        retry_at = e.get("retry_at")
        eds.append(
            {
                "lang": lang,
                "state": e["state"],
                "pct": 100 if e["state"] == "done" else int(e["pct"] or 0),
                "error": e.get("error"),
                "retry_at": iso(retry_at) if retry_at and e.get("error") == "rate_limited" else None,
            }
        )
    return {
        "job_id": job["qid"],
        "qid": job["qid"],
        "topic_id": job["topic_id"],
        "title": job["title"],
        "state": job["state"],
        "eta_s": eta_left(job, eds),
        "since": job["since"].isoformat() if job.get("since") else None,
        "editions": eds,
    }


def eta_left(job: dict, eds: list[dict]) -> int | None:
    """Seconds left: the creation estimate until a fifth of the work is done, then elapsed time scaled by progress."""
    if job["state"] in ("done", "failed"):
        return None
    live = [e for e in eds if e["error"] != "no_article"]
    pct = sum(e["pct"] if e["state"] != "failed" else 100 for e in live) / max(1, len(live))
    started = job.get("started_at")
    if started and pct >= 20:
        elapsed = (now() - started).total_seconds()
        return max(5, int(elapsed * (100 - pct) / pct))
    return job.get("eta_s")


def loaded_view(topic: dict, pages: list[dict]) -> dict:
    """A topic that is in the database without a job (seed topics): done, with every edition it has."""
    have = {p["lang"] for p in pages}
    return {
        "job_id": topic["wikidata_id"],
        "qid": topic["wikidata_id"],
        "topic_id": topic["topic_id"],
        "title": topic["label_en"],
        "state": "done",
        "eta_s": None,
        "since": None,
        "editions": [
            {
                "lang": lang,
                "state": "done" if lang in have else "failed",
                "pct": 100 if lang in have else 0,
                "error": None if lang in have else "no_article",
                "retry_at": None,
            }
            for lang in LANGS
        ],
    }


def status(cur, qid: str) -> dict | None:
    jobs = _q(cur, "SELECT * FROM ingest_job WHERE qid=%s", (qid,))
    if jobs:
        return job_view(jobs[0], _q(cur, "SELECT * FROM ingest_edition WHERE qid=%s", (qid,)))
    topics = _q(cur, "SELECT * FROM topic WHERE wikidata_id=%s", (qid,))
    if topics:
        return loaded_view(topics[0], _q(cur, "SELECT lang FROM page WHERE topic_id=%s", (topics[0]["topic_id"],)))
    return None


# ---------------------------------------------------------------- one edition: fetch


def fetch_edition(lang: str, title: str, since: dt.date | None, progress) -> dict:
    """Revision metadata and the snapshot texts of one edition from the API (cached on disk by wapi)."""
    since_ts = f"{since.isoformat()}T00:00:00Z" if since else None
    params = {
        "prop": "revisions|info",
        "titles": title,
        "rvprop": "ids|timestamp|size|flags|sha1|comment",
        "rvlimit": "max",
        "rvdir": "newer",
        "redirects": 1,
    }
    if since_ts:
        params["rvstart"] = since_ts
    page_id, length, meta, n = None, None, [], 0
    for body in wapi.query_all(lang, params, max_age_s=wapi.DAY_S):  # history grows: a later load sees new edits
        pages = body["query"]["pages"]
        if not pages or "missing" in pages[0]:
            raise LookupError(f"{lang}: no page {title!r}")
        page = pages[0]
        page_id, length = page["pageid"], page.get("length")
        meta.extend(meta_row(r) for r in page.get("revisions", []))
        n += 1
        progress(min(25, 5 + 4 * n))
    if since_ts:  # the revision that was current on `since` opens the window
        body = wapi.get(
            wapi.api_url(lang),
            {
                "action": "query",
                "prop": "revisions",
                "titles": title,
                "rvprop": "ids|timestamp|size|flags|sha1|comment",
                "rvlimit": 1,
                "rvdir": "older",
                "rvstart": since_ts,
                "redirects": 1,
                "formatversion": 2,
            },
            max_age_s=wapi.DAY_S,
        )
        meta = [meta_row(r) for r in body["query"]["pages"][0].get("revisions", [])] + meta
    if not meta:
        raise LookupError(f"{lang}: {title!r} has no revisions")
    meta.sort(key=lambda r: r["ts"])
    picks = pick_snapshots(meta)
    texts = []
    for i in range(0, len(picks), 10):
        texts.extend(fetch_texts(lang, picks[i : i + 10]))
        progress(25 + int(10 * min(1.0, (i + 10) / len(picks))))
    return {"lang": lang, "title": title, "page_id": page_id, "length": length, "meta": meta, "snaps": texts}


def current_length(lang: str, title: str) -> int:
    body = wapi.get(
        wapi.api_url(lang),
        {"action": "query", "prop": "info", "titles": title, "redirects": 1, "formatversion": 2},
        max_age_s=wapi.DAY_S,
    )
    pages = body.get("query", {}).get("pages", [])
    return int(pages[0].get("length") or 0) if pages and "missing" not in pages[0] else 0


# ---------------------------------------------------------------- one edition: parse, embed, load


_STORE = None
_STORE_LOCK = threading.Lock()


def embed(texts: list[str], progress) -> list[np.ndarray]:
    """bge-m3 through engine.embed (vectors kept under data/emb/), or sketch_embed with EMBED_BACKEND=fake."""
    if os.environ.get("EMBED_BACKEND") == "fake":
        return [np.asarray(v, dtype=np.float32) for v in sketch_embed(texts)]
    from engine.embed import embed_texts, writer

    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = writer()  # shares the API's vectors in memory instead of loading data/emb/ a second time
        return embed_texts(texts, _STORE, progress=progress)


def lives_of(fetched: dict):
    cache = ParseCache()
    revs = []
    for r in fetched["snaps"]:
        p = cache.get(r.get("sha1"), r["text"])
        revs.append({**{k: r.get(k) for k in ("rev_id", "ts", "sha1", "comment")}, "sentences": p.sentences})
    return walk(revs, exact=False)


def load_edition(conn, topic_id: str, fetched: dict, w, vecs: dict) -> int:
    """Page, revisions, section versions and sentence lives of one edition in one transaction."""
    lang, pid = fetched["lang"], fetched["page_id"]
    parsed = {r["rev_id"] for r in fetched["snaps"]}
    cur = conn.cursor()
    conn.begin()
    try:
        cur.execute("SET system_versioning_insert_history=1")
        cur.execute(
            "INSERT INTO page (lang, page_id, topic_id, title, source, history) VALUES (%s,%s,%s,%s,'api','yearly') "
            "ON DUPLICATE KEY UPDATE topic_id=VALUES(topic_id), title=VALUES(title), source='api', history='yearly'",
            (lang, pid, topic_id, fetched["title"][:255]),
        )
        rows = (
            (lang, r["rev_id"], pid, r.get("parent_id") or None, r["ts"].replace("T", " ").rstrip("Z"), r.get("bytes"),
             r.get("minor", 0), (r.get("comment") or None) and r["comment"][:1000], int(r["rev_id"] in parsed))
            for r in fetched["meta"]
        )  # fmt: skip
        cols = ["lang", "rev_id", "page_id", "parent_id", "ts", "bytes", "minor", "comment", "snapshot"]
        sql = f"INSERT IGNORE INTO revision ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})"
        rows = list(rows)
        for i in range(0, len(rows), 500):
            cur.executemany(sql, rows[i : i + 500])
        secs = [{**s, "topic_id": topic_id, "lang": lang, "section": s["section"][:255]} for s in w.sections]
        versioned(cur, "section_text", ["topic_id", "lang", "section", "rev_id", "n_sent", "text"], secs)
        claims = [
            {**lv, "lang": lang, "page_id": pid, "topic_id": topic_id, "section": lv["section"][:255],
             "died_comment": (lv["died_comment"] or None) and lv["died_comment"][:1000],
             "emb": np.asarray(vecs[lv["h"]], dtype="<f4").tobytes()}
            for lv in w.lives
        ]  # fmt: skip
        cols = ["lang", "page_id", "h", "topic_id", "section", "text", "born_rev", "died_rev", "died_comment",
                "time_precision", "has_ref", "had_ref", "emb"]  # fmt: skip
        n = versioned(cur, "claim", cols, claims)
        conn.commit()
        return n
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.execute("SET system_versioning_insert_history=0")
        cur.close()


# ---------------------------------------------------------------- align and judge


def align_dates(cur) -> list[tuple[str, str]]:
    """The dates the align cache already holds (other topics), with the instant to cut at. Only those dates get rows
    for the new topic: /api/compare reads the cache for a date as soon as any row of that date exists."""
    cur.execute("SELECT DISTINCT as_of FROM align ORDER BY as_of")
    today = now().date()
    out = []
    for (d,) in cur.fetchall():
        inst = now().strftime("%Y-%m-%d %H:%M:%S") if d >= today else f"{d} 00:00:00"
        out.append((d.isoformat(), inst))
    return out


def align_edition(cur, topic_id: str, lang: str, loaded: list[str]) -> int:
    """Cached nearest candidates between Finnish and this edition, both directions, on every cached date."""
    others = [lang] if lang != "fi" else [x for x in loaded if x != "fi"]
    pairs = [p for x in others for p in (("fi", x), (x, "fi"))]
    n = 0
    for as_of, inst in align_dates(cur):
        for src, dst in pairs:
            cur.execute(ALIGN_SQL, (as_of, inst, inst, topic_id, src, topic_id, dst))
            n += cur.rowcount
    return n


def judge_tasks(cur, topic_id: str, lang: str, prompt_version: str) -> list[dict]:
    """The first JUDGE_CLAIMS Finnish statements alive now, in Compare order, with their nearest statements in
    `lang` that are not judged yet."""
    cur.execute(
        "SELECT a.h, a.page_id, a.text FROM claim a LEFT JOIN section_text s ON s.topic_id=a.topic_id "
        "AND s.lang=a.lang AND s.section=a.section WHERE a.topic_id=%s AND a.lang='fi' "
        "ORDER BY CASE a.section WHEN '[infobox]' THEN 0 WHEN '[lead]' THEN 1 ELSE 2 END, a.section IN %s, a.section, "
        "LOCATE(a.text, s.text), a.h LIMIT %s",
        (topic_id, TAIL_SECTIONS, JUDGE_CLAIMS),
    )
    claims = {h: {"a_h": h, "text": text, "candidates": []} for h, _pid, text in cur.fetchall()}
    if not claims:
        return []
    cur.execute(
        f"""SELECT src_h, page_id, h, text FROM (
              SELECT a.h AS src_h, b.page_id, b.h, b.text,
                     ROW_NUMBER() OVER (PARTITION BY a.h ORDER BY VEC_DISTANCE_COSINE(b.emb, a.emb), b.h) AS rk
              FROM claim a JOIN claim b IGNORE INDEX (emb) ON b.topic_id=a.topic_id AND b.lang=%s
              WHERE a.topic_id=%s AND a.lang='fi' AND a.h IN %s) x
            WHERE rk <= {JUDGE_CANDIDATES} ORDER BY src_h, rk""",
        (lang, topic_id, tuple(claims)),
    )
    cands = cur.fetchall()
    cur.execute(
        "SELECT a_h, b_h FROM verdict WHERE a_lang='fi' AND b_lang=%s AND prompt_version=%s AND a_h IN %s",
        (lang, prompt_version, tuple(claims)),
    )
    done = set(cur.fetchall())
    for src_h, pid, h, text in cands:
        if (src_h, h) not in done:
            claims[src_h]["candidates"].append(Candidate(lang, pid, h, text))
    return [c for c in claims.values() if c["candidates"]]


class Counter:
    def __init__(self) -> None:
        self.calls = 0
        self.pairs = 0
        self.lock = threading.Lock()

    def add(self, calls: int, pairs: int = 0) -> None:
        with self.lock:
            self.calls += calls
            self.pairs += pairs


def judge_edition(cur, topic_id: str, lang: str, eng, counter: Counter) -> list[tuple[str, str]]:
    """Judge fi statements against `lang`; returns (lang, h) of the matched sentences (for glosses)."""
    tasks = judge_tasks(cur, topic_id, lang, eng.prompt_version)
    matched: list[tuple[str, str]] = []
    if not tasks:
        return matched

    def one(t):
        if eng.name == "fake":
            return t, eng.judge_or_guess(t["text"], "fi", t["candidates"])
        return t, [(v, eng.model_id) for v in eng.judge(t["text"], "fi", t["candidates"])]

    rows = []
    workers = 1 if eng.name == "fake" else 4
    with ThreadPoolExecutor(workers) as pool:
        for fut in [pool.submit(one, t) for t in tasks]:
            try:
                t, verdicts = fut.result()
            except Exception as e:  # stays unjudged: Compare shows the nearest candidate
                log.warning("judge failed for %s: %s", lang, type(e).__name__)
                counter.add(1)
                continue
            counter.add(0 if eng.name == "fake" else 1, len(verdicts))
            for c, (v, model) in zip(t["candidates"], verdicts, strict=True):
                rows.append(
                    ("fi", t["a_h"], lang, c.h, eng.prompt_version, v.label,
                     _json(v.numbers), _json(v.terms), model,
                     _json({"label": v.label, "numbers": v.numbers, "terms": v.terms, "note": v.note}))
                )  # fmt: skip
                if v.label in ("same", "partial", "contradicts"):
                    matched.append((lang, c.h))
    cur.executemany(
        "INSERT INTO verdict (a_lang, a_h, b_lang, b_h, prompt_version, label, numbers, terms, model, raw, judged_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP(6)) "
        "ON DUPLICATE KEY UPDATE label=VALUES(label), numbers=VALUES(numbers), terms=VALUES(terms)",
        rows,
    )
    return matched


def _json(x) -> str:
    import json

    return json.dumps(x, ensure_ascii=False)


def gloss(cur, topic_id: str, keys: list[tuple[str, str]], eng, counter: Counter) -> int:
    """English glosses for (lang, h) without one; real engine only (the fake engine has no translations)."""
    if eng.name != "real" or not keys:
        return 0
    by_lang: dict[str, set[str]] = {}
    for lang, h in keys:
        if lang != "en":
            by_lang.setdefault(lang, set()).add(h)
    n = 0
    for lang, hs in by_lang.items():
        cur.execute(
            "SELECT DISTINCT c.h, c.text FROM claim FOR SYSTEM_TIME ALL c LEFT JOIN gloss g ON g.lang=c.lang "
            "AND g.h=c.h WHERE c.topic_id=%s AND c.lang=%s AND c.h IN %s AND g.h IS NULL",
            (topic_id, lang, tuple(hs)),
        )
        items = list({h: t for h, t in cur.fetchall()}.items())
        for i in range(0, len(items), GLOSS_BATCH):
            chunk = items[i : i + GLOSS_BATCH]
            counter.add(1)
            try:
                out = eng.gloss([t for _, t in chunk], lang)
            except Exception as e:
                log.warning("gloss failed for %s: %s", lang, type(e).__name__)
                continue
            cur.executemany(
                "INSERT INTO gloss (lang, h, text_en, model) VALUES (%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE text_en=VALUES(text_en), model=VALUES(model)",
                [(lang, h, g, eng.model_id) for (h, _), g in zip(chunk, out, strict=True)],
            )
            n += len(chunk)
    return n


# ---------------------------------------------------------------- the job


class Stopped(Exception):
    pass


class Job:
    def __init__(self, qid: str, stop: threading.Event | None = None, echo=None) -> None:
        self.qid = qid
        self.stop = stop or threading.Event()
        self.echo = echo or (lambda s: log.info(s))
        self.conn = connect()
        self.cur = self.conn.cursor()
        self.counter = Counter()
        self._lock = threading.Lock()  # one connection, used by the fetch thread and the main thread
        self.t0 = time.time()

    def sql(self, text: str, params=()) -> list[dict]:
        with self._lock:
            return _q(self.cur, text, params)

    def ed(self, lang: str, **fields) -> None:
        sets = ", ".join(f"{k}=%s" for k in fields)
        self.sql(f"UPDATE ingest_edition SET {sets} WHERE qid=%s AND lang=%s", (*fields.values(), self.qid, lang))

    def job(self, **fields) -> None:
        fields["updated_at"] = now()
        sets = ", ".join(f"{k}=%s" for k in fields)
        self.sql(f"UPDATE ingest_job SET {sets} WHERE qid=%s", (*fields.values(), self.qid))

    # -- fetch side (runs in the prefetch thread)

    def fetch(self, lang: str, title: str, since):
        def waiting(seconds: float) -> None:
            self.ed(lang, error="rate_limited", retry_at=now() + dt.timedelta(seconds=seconds))

        def progress(pct: int) -> None:
            self.ed(lang, pct=pct, error=None, retry_at=None)

        wapi.on_wait(waiting)
        try:
            self.ed(lang, state="running", pct=2)
            latest = self.sql("SELECT since FROM ingest_job WHERE qid=%s", (self.qid,))
            since = latest[0]["since"] if latest else since  # a later POST may have narrowed it
            return fetch_edition(lang, title, since, progress)
        finally:
            wapi.on_wait(None)

    # -- the rest (main thread)

    def process(self, topic_id: str, lang: str, fetched: dict, eng) -> None:
        t = time.time()
        self.ed(lang, page_id=fetched["page_id"], length=fetched["length"], revisions=len(fetched["meta"]),
                snapshots=len(fetched["snaps"]), pct=36, error=None, retry_at=None)  # fmt: skip
        already = self.sql(
            "SELECT COUNT(*) AS n FROM claim FOR SYSTEM_TIME ALL WHERE lang=%s AND page_id=%s",
            (lang, fetched["page_id"]),
        )[0]["n"]
        if already:  # loaded before a crash or a stop: keep the rows
            n = int(already)
        else:
            w = lives_of(fetched)
            self.ed(lang, pct=40)
            texts = list({lv["h"]: lv["text"] for lv in w.lives}.items())

            def prog(done: int, total: int) -> None:
                self.ed(lang, pct=40 + int(40 * done / max(1, total)))
                if self.stop.is_set():
                    raise Stopped()

            vs = embed([x for _, x in texts], prog)
            vecs = {h: v for (h, _), v in zip(texts, vs, strict=True)}
            self.ed(lang, pct=82)
            with self._lock:
                n = load_edition(self.conn, topic_id, fetched, w, vecs)
        self.ed(lang, pct=88, statements=n)
        loaded = [r["lang"] for r in self.sql(
            "SELECT lang FROM ingest_edition WHERE qid=%s AND state='done'", (self.qid,))] + [lang]  # fmt: skip
        with self._lock:
            align_edition(self.cur, topic_id, lang, loaded)
        self.ed(lang, pct=92)
        others = [lang] if lang != "fi" else [x for x in loaded if x != "fi"]
        for other in others:
            with self._lock:
                matched = judge_edition(self.cur, topic_id, other, eng, self.counter)
                gloss(self.cur, topic_id, matched, eng, self.counter)
        self.ed(lang, state="done", pct=100, error=None, retry_at=None, seconds=round(time.time() - t, 1))
        self.job(model_calls=self.counter.calls, judge_pairs=self.counter.pairs)
        self.echo(
            f"{self.qid} {lang} done: revisions={len(fetched['meta'])} snapshots={len(fetched['snaps'])} "
            f"statements={n} t={time.time() - self.t0:.0f}s model_calls={self.counter.calls}"
        )

    def mark_usable(self) -> None:
        rows = self.sql("SELECT lang FROM ingest_edition WHERE qid=%s AND state='done'", (self.qid,))
        done = {r["lang"] for r in rows}
        if "fi" in done and len(done) >= 2:
            j = self.sql("SELECT state FROM ingest_job WHERE qid=%s", (self.qid,))[0]
            if j["state"] == "running":
                self.job(state="usable", usable_at=now())
                self.echo(f"{self.qid} usable after {time.time() - self.t0:.0f}s")

    def run(self) -> str:
        (got,) = self.sql("SELECT GET_LOCK(%s, 0) AS got", (f"px_ingest_{self.qid}",))[0].values()
        if not got:
            return "locked"
        try:
            return self._run()
        finally:
            self.sql("SELECT RELEASE_LOCK(%s)", (f"px_ingest_{self.qid}",))
            self.conn.close()

    def _run(self) -> str:
        jobs = self.sql("SELECT * FROM ingest_job WHERE qid=%s", (self.qid,))
        if not jobs:
            return "missing"
        job = jobs[0]
        if job["state"] in ("done", "failed"):
            return job["state"]
        topic_id, since = job["topic_id"], job["since"]
        self.job(state="usable" if job["state"] == "usable" else "running", started_at=job["started_at"] or now())
        self.sql(
            "INSERT INTO topic (topic_id, wikidata_id, label_en, depth) VALUES (%s,%s,%s,'deep') "
            "ON DUPLICATE KEY UPDATE label_en=VALUES(label_en)",
            (topic_id, self.qid, job["title"]),
        )
        eng = get_engine()
        self.echo(f"{self.qid} {job['title']!r} topic={topic_id} engine={eng.name} since={since}")
        for _round in range(MAX_TRIES + 1):
            eds = self.sql(
                "SELECT * FROM ingest_edition WHERE qid=%s AND title IS NOT NULL AND state<>'done'", (self.qid,)
            )
            eds = [e for e in eds if not (e["state"] == "failed" and e["error"] != "rate_limited")]
            eds = [e for e in eds if e["tries"] < MAX_TRIES]
            if not eds:
                break
            wait = max([(e["retry_at"] - now()).total_seconds() for e in eds if e["retry_at"]] or [0])
            if wait > 0 and all(e["error"] == "rate_limited" for e in eds):
                self.echo(f"{self.qid} waiting {wait:.0f}s for Wikipedia")
                if self.stop.wait(wait):
                    return "stopped"
            self._round(topic_id, since, eds, eng)
            if self.stop.is_set():
                return "stopped"
        rows = self.sql("SELECT lang, state FROM ingest_edition WHERE qid=%s", (self.qid,))
        fi_done = any(r["lang"] == "fi" and r["state"] == "done" for r in rows)
        for r in rows:  # anything left over gave up
            if r["state"] in ("waiting", "running"):
                self.ed(r["lang"], state="failed", error=r.get("error") or "gave_up")
        state = "done" if fi_done else "failed"
        self.job(state=state, done_at=now(), model_calls=self.counter.calls, judge_pairs=self.counter.pairs,
                 error=None if fi_done else "Finnish edition could not load")  # fmt: skip
        if not fi_done:
            self.sql("DELETE FROM topic WHERE topic_id=%s AND NOT EXISTS (SELECT 1 FROM page WHERE topic_id=%s)",
                     (topic_id, topic_id))  # fmt: skip
        self.echo(
            f"{self.qid} {state} after {time.time() - self.t0:.0f}s model_calls={self.counter.calls} "
            f"judge_pairs={self.counter.pairs} {wapi.stats_line()}"
        )
        return state

    def _round(self, topic_id: str, since, eds: list[dict], eng) -> None:
        # Finnish first, then the smallest article first so the comparison opens early.
        lengths = {}
        for e in eds:
            if e["lang"] != "fi":
                try:
                    lengths[e["lang"]] = e["length"] or current_length(e["lang"], e["title"])
                except wapi.WikiError:
                    lengths[e["lang"]] = 10**9
        eds.sort(key=lambda e: (e["lang"] != "fi", lengths.get(e["lang"], 0)))
        fi_ok = bool(self.sql("SELECT 1 FROM ingest_edition WHERE qid=%s AND lang='fi' AND state='done'", (self.qid,)))
        with ThreadPoolExecutor(1) as pool:
            futs = [(e, pool.submit(self.fetch, e["lang"], e["title"], since)) for e in eds]
            for e, fut in futs:
                lang = e["lang"]
                if self.stop.is_set():
                    fut.cancel()
                    continue
                try:
                    if lang != "fi" and not fi_ok:
                        fut.result()  # keep the download; process it once Finnish is in
                        self.ed(lang, state="waiting", pct=0)
                        continue
                    self.process(topic_id, lang, fut.result(), eng)
                    fi_ok = fi_ok or lang == "fi"
                    self.mark_usable()
                except Stopped:
                    self.ed(lang, state="waiting", pct=0)
                except wapi.RateLimited as ex:
                    self.ed(lang, state="failed", error="rate_limited", tries=e["tries"] + 1,
                            retry_at=now() + dt.timedelta(seconds=ex.retry_after_s))  # fmt: skip
                    self.echo(f"{self.qid} {lang} rate limited, retry in {ex.retry_after_s:.0f}s")
                except Exception as ex:
                    log.warning("ingest %s %s failed:\n%s", self.qid, lang, traceback.format_exc())
                    self.ed(lang, state="failed", error=type(ex).__name__[:64], tries=e["tries"] + 1)
                    self.echo(f"{self.qid} {lang} failed: {type(ex).__name__}: {ex}")


def run_job(qid: str, stop: threading.Event | None = None, echo=None) -> str:
    return Job(qid, stop, echo).run()


# ---------------------------------------------------------------- the worker thread of the API


class Worker:
    """One job at a time, oldest first. Jobs left running by a stopped process are picked up again (resumable:
    finished editions are kept)."""

    def __init__(self, after_job: Callable[[], None] | None = None) -> None:
        self.after_job = after_job  # e.g. the API clears its response cache, the job changed what it serves
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.thread: threading.Thread | None = None
        self.failures: dict[str, int] = {}  # qid -> crashes in a row

    def start(self) -> None:
        self.thread = threading.Thread(target=self._loop, name="ingest-worker", daemon=True)
        self.thread.start()

    def notify(self) -> None:
        self.wake.set()

    def close(self, timeout: float = 10) -> None:
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout)

    def _next(self) -> str | None:
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT qid FROM ingest_job WHERE state IN ('queued','running','usable') "
                    "AND IS_FREE_LOCK(CONCAT('px_ingest_', qid)) ORDER BY created_at LIMIT 1"
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    def _crashed(self, qid: str) -> None:
        """Count a crash of qid; after MAX_JOB_FAILURES in a row the job is marked failed so the worker moves on."""
        n = self.failures.get(qid, 0) + 1
        self.failures[qid] = n
        log.warning("ingest %s crashed (%d of %d):\n%s", qid, n, MAX_JOB_FAILURES, traceback.format_exc())
        if n < MAX_JOB_FAILURES:
            return
        self.failures.pop(qid, None)
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ingest_job SET state='failed', error=%s, done_at=%s, updated_at=%s "
                    "WHERE qid=%s AND state IN ('queued','running','usable')",
                    ("The load stopped with an error.", now(), now(), qid),
                )
                slug = topic_slug(qid)  # a topic row without any page would list an empty article
                cur.execute(
                    "DELETE FROM topic WHERE topic_id=%s AND NOT EXISTS (SELECT 1 FROM page WHERE topic_id=%s)",
                    (slug, slug),
                )
        finally:
            conn.close()
        log.error("ingest %s marked failed after %d crashes", qid, MAX_JOB_FAILURES)

    def _loop(self) -> None:
        while not self.stop.is_set():
            qid = None
            try:
                qid = self._next()
                if qid:
                    try:
                        run_job(qid, self.stop)
                        self.failures.pop(qid, None)
                    finally:
                        if self.after_job:
                            self.after_job()
                    continue
            except Exception:
                if qid:
                    try:
                        self._crashed(qid)
                    except Exception:
                        log.warning("ingest worker could not mark %s:\n%s", qid, traceback.format_exc())
                else:
                    log.warning("ingest worker:\n%s", traceback.format_exc())
            self.wake.wait(5)
            self.wake.clear()


# ---------------------------------------------------------------- command line


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Wikidata items (qids) one after another; resumable.")
    ap.add_argument("qids", nargs="+")
    ap.add_argument("--since", help="history only from this date (YYYY-MM-DD)")
    a = ap.parse_args()
    ensure_tables()
    total = 0
    for qid in a.qids:
        qid = qid.strip().upper()
        conn = connect()
        with conn.cursor() as cur:
            try:
                what = create(cur, qid, a.since)
            except NoFinnish:
                print(f"{qid}: no Finnish article, skipped", flush=True)
                continue
            except UnknownItem:
                print(f"{qid}: no such Wikidata item, skipped", flush=True)
                continue
        conn.close()
        if what == "loaded":
            print(f"{qid}: already loaded, skipped", flush=True)
            continue
        t = time.time()
        job = Job(qid, echo=lambda s: print(s, flush=True))
        state = job.run()
        total += job.counter.calls
        print(f"{qid}: {state} in {time.time() - t:.0f}s, model calls {job.counter.calls}", flush=True)
    print(f"model calls in total: {total}", flush=True)


if __name__ == "__main__":
    main()
