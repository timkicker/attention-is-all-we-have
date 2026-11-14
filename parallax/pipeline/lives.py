"""A4: ordered revisions of one page -> sentence lives (rebirths included) and section versions.

Exact lives (every revision) get the noise rule from PLAN section 2: gaps under 24 hours or closed by a revert
are healed, then lives under 24 hours or ended by a revert to a revision older than their birth are dropped.

Snapshot editions walk the yearly snapshots plus the extra revisions A5 (pipeline/bisect.py) fetched around each
demo edit. A sample that directly follows the previous sample in page history is "adjacent": a sentence born or
gone there changed in exactly that edit. Because every sample is a whole page, the sentence that replaces a claim
is born at the same instant the claim dies, so an edition never goes silent between two samples.
"""

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pipeline.fetch import DATA, hist_dir, read_jsonl, write_jsonl
from pipeline.parse import ParseCache, revisions

NOISE = timedelta(hours=24)
US = timedelta(microseconds=1)
TS_FMT = "%Y-%m-%d %H:%M:%S.%f"


def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts.replace("T", " ").rstrip("Z")[:19], "%Y-%m-%d %H:%M:%S")


def fmt(dt: datetime | None) -> str | None:
    return dt.strftime(TS_FMT) if dt else None


@dataclass
class Walk:
    lives: list[dict] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    revs: list[dict] = field(default_factory=list)  # rev_id, ts (strictly increasing), comment
    counts: dict = field(default_factory=dict)


def revert_targets(sha1s: list[str | None]) -> dict[int, int]:
    """index of a revert -> index of the revision it restores (same sha1, earlier, not the parent)."""
    last_seen: dict[str, int] = {}
    out = {}
    for i, s in enumerate(sha1s):
        if s and i > 0 and sha1s[i - 1] != s and s in last_seen:
            out[i] = last_seen[s]
        if s:
            last_seen[s] = i
    return out


def walk(revs: list[dict], exact: bool) -> Walk:
    """revs: time-ordered dicts with rev_id, ts, sha1, comment, sentences [{h, text, section, has_ref}].

    With exact=False a rev may carry adjacent=True (it is the direct successor of the previous rev in page history).
    A life whose death is at an adjacent rev, or that is alive and was born at one, gets time_precision 'exact' and
    the died_comment of that rev; every other snapshot life keeps 'snapshot'."""
    out = Walk()
    adj = [True if exact else bool(r.get("adjacent")) for r in revs]
    ts: list[datetime] = []
    for r in revs:
        t = parse_ts(r["ts"])
        if ts and t <= ts[-1]:
            t = ts[-1] + US
        ts.append(t)
        out.revs.append({"rev_id": r["rev_id"], "ts": t, "comment": r.get("comment")})
    reverts = revert_targets([r.get("sha1") for r in revs]) if exact else {}

    # raw walk: per h a list of [born_idx, died_idx|None, text, section, had_ref, has_ref]
    raw: dict[str, list[list]] = {}
    alive: dict[str, list] = {}
    sec_cur: dict[str, tuple[str, int, int, str]] = {}  # section -> (digest, born_idx, n_sent, text)
    sec_rows: list[dict] = []
    for i, r in enumerate(revs):
        cur = {}
        by_sec: dict[str, list[str]] = {}
        for s in r["sentences"]:
            cur.setdefault(s["h"], s)
            by_sec.setdefault(s["section"], []).append(s["text"])
        for h in [h for h in alive if h not in cur]:
            alive.pop(h)[1] = i
        for h, s in cur.items():
            life = alive.get(h)
            if life is None:
                life = [i, None, s["text"], s["section"], bool(s["has_ref"]), bool(s["has_ref"])]
                alive[h] = life
                raw.setdefault(h, []).append(life)
            else:
                life[3] = s["section"]
                life[5] = bool(s["has_ref"])
                life[4] = life[4] or life[5]
        # section versions
        for name in [n for n in sec_cur if n not in by_sec]:
            _digest, born, n, text = sec_cur.pop(name)
            sec_rows.append({"section": name, "born": born, "died": i, "n_sent": n, "text": text})
        for name, sents in by_sec.items():
            text = "\n".join(sents)
            digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
            prev = sec_cur.get(name)
            if prev and prev[0] == digest:
                continue
            if prev:
                sec_rows.append({"section": name, "born": prev[1], "died": i, "n_sent": prev[2], "text": prev[3]})
            sec_cur[name] = (digest, i, len(sents), text)
    for name, (_digest, born, n, text) in sec_cur.items():
        sec_rows.append({"section": name, "born": born, "died": None, "n_sent": n, "text": text})

    n_raw = sum(len(v) for v in raw.values())
    healed = noise = 0
    final: list[tuple[str, list]] = []
    for h, lives in raw.items():
        if exact:
            merged = [lives[0]]
            for nxt in lives[1:]:
                prev = merged[-1]
                gap_short = ts[nxt[0]] - ts[prev[1]] < NOISE
                tgt = reverts.get(nxt[0])
                restores_alive = tgt is not None and prev[0] <= tgt < prev[1]
                if gap_short or restores_alive:
                    prev[1] = nxt[1]
                    prev[2], prev[3], prev[5] = nxt[2], nxt[3], nxt[5]
                    prev[4] = prev[4] or nxt[4]
                    healed += 1
                else:
                    merged.append(nxt)
            lives = []
            for lv in merged:
                if lv[1] is not None:
                    short = ts[lv[1]] - ts[lv[0]] < NOISE
                    tgt = reverts.get(lv[1])
                    undone = tgt is not None and tgt < lv[0]
                    if short or undone:
                        noise += 1
                        continue
                lives.append(lv)
        final.extend((h, lv) for lv in lives)

    for h, (b, d, text, section, had_ref, has_ref) in final:
        died_exact = d is not None and adj[d]
        precise = died_exact or (d is None and adj[b])
        out.lives.append(
            {
                "h": h,
                "text": text,
                "section": section,
                "born_rev": revs[b]["rev_id"],
                "row_start": fmt(ts[b]),
                "died_rev": revs[d]["rev_id"] if d is not None else None,
                "row_end": fmt(ts[d]) if d is not None else None,
                "died_comment": (revs[d].get("comment") or None) if died_exact else None,
                "time_precision": "exact" if precise else "snapshot",
                "has_ref": int(has_ref),
                "had_ref": int(had_ref),
            }
        )
    out.lives.sort(key=lambda lv: (lv["row_start"], lv["h"]))
    for s in sec_rows:
        out.sections.append(
            {
                "section": s["section"],
                "rev_id": revs[s["born"]]["rev_id"],
                "n_sent": s["n_sent"],
                "text": s["text"],
                "row_start": fmt(ts[s["born"]]),
                "row_end": fmt(ts[s["died"]]) if s["died"] is not None else None,
            }
        )
    alive_n = sum(1 for lv in out.lives if lv["died_rev"] is None)
    out.counts = {
        "lives": len(out.lives),
        "alive": alive_n,
        "dead": len(out.lives) - alive_n,
        "distinct": len({lv["h"] for lv in out.lives}),
        "lives_raw": n_raw,
        "lives_noise": noise,
        "gaps_healed": healed,
        "reverts": len(reverts),
    }
    for r in out.revs:
        r["ts"] = fmt(r["ts"])
    return out


def meta_order(topic: str, lang: str) -> list[dict]:
    """Revision metadata of one edition in page-history order (the order bisect and the samples use)."""
    return sorted(read_jsonl(hist_dir(topic) / f"{lang}.meta.jsonl.gz"), key=lambda r: r["ts"])


def extra_path(topic: str, lang: str):
    return hist_dir(topic) / f"{lang}.extra.jsonl.gz"


def samples(topic: str, lang: str, exact: bool, extra: list[dict] | None = None) -> list[dict]:
    """Revisions with text the walk goes over, in page-history order. Snapshot editions add the extra revisions
    (from `extra`, else from <lang>.extra.jsonl.gz written by bisect) and mark each sample adjacent or not."""
    revs = list(revisions(topic, lang))
    if exact:
        return revs
    if extra is None:
        p = extra_path(topic, lang)
        extra = list(read_jsonl(p)) if p.exists() else []
    if not extra:
        return revs
    pos = {r["rev_id"]: i for i, r in enumerate(meta_order(topic, lang))}
    by_id = {r["rev_id"]: r for r in revs}
    for r in extra:
        by_id.setdefault(r["rev_id"], r)
    out = [dict(r) for r in sorted(by_id.values(), key=lambda r: (pos.get(r["rev_id"], -1), r["ts"]))]
    prev = None
    for r in out:
        q = pos.get(r["rev_id"])
        r["adjacent"] = prev is not None and q is not None and q == prev + 1
        prev = q
    return out


def page_walk(topic: str, lang: str, exact: bool, extra: list[dict] | None = None) -> tuple[Walk, ParseCache]:
    cache = ParseCache()
    revs = []
    for r in samples(topic, lang, exact, extra):
        p = cache.get(r.get("sha1"), r["text"])
        keep = {k: r.get(k) for k in ("rev_id", "ts", "sha1", "comment", "adjacent")}
        revs.append({**keep, "sentences": p.sentences})
    return walk(revs, exact), cache


def lives_dir():
    return DATA / "lives"


def main(topic: str) -> None:
    pages = json.loads((hist_dir(topic) / "pages.json").read_text(encoding="utf-8"))
    stats = {}
    print(f"{'lang':5} {'lives':>6} {'alive':>6} {'dead':>6} {'distinct':>8} {'raw':>6} {'noise':>6} {'healed':>6}")
    for lang, page in pages.items():
        exact = page["history"] == "every"
        w, cache = page_walk(topic, lang, exact)
        write_jsonl(lives_dir() / f"{topic}-{lang}.jsonl.gz", w.lives)
        write_jsonl(lives_dir() / f"{topic}-{lang}.sections.jsonl.gz", w.sections)
        c = w.counts | {"parsed": cache.parsed, "cache_hits": cache.cache_hits, "exact": exact}
        stats[lang] = c
        print(
            f"{lang:5} {c['lives']:6} {c['alive']:6} {c['dead']:6} {c['distinct']:8} {c['lives_raw']:6} "
            f"{c['lives_noise']:6} {c['gaps_healed']:6}"
        )
    (lives_dir() / f"{topic}-stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    main(ap.parse_args().topic)
