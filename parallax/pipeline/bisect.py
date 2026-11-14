"""A5: the exact edit, date and comment for every claim the demo shows changing.

Lives of the six API editions have yearly snapshot bounds. For each (lang, regex) in demo_claims.yaml we binary
search the revision metadata between two snapshots, fetching single revisions (cached). A disappearance that is
undone within 24 hours (vandalism, PLAN noise rule) is skipped and the search continues after it.

The edit and the revision before it become extra samples of that edition (data/hist/<topic>/<lang>.extra.jsonl.gz)
and its lives are rebuilt over snapshots plus extras (pipeline.lives.samples), so the claim's death, its replacement's
birth and the comment all come from the same edit. A wording the edit added that is gone again by the next sample is
chased the same way, so the slider never shows a stale or empty cell right after a demo edit.
"""

import argparse
import json
import re
from collections.abc import Callable
from functools import cache

import yaml

from pipeline import wapi
from pipeline.fetch import ROOT, hist_dir, read_jsonl, write_jsonl
from pipeline.lives import extra_path, lives_dir, meta_order, page_walk, parse_ts, samples
from pipeline.parse import parse

MAX_ROUNDS = 8  # chase rounds per edition
MAX_EXTRA = 400  # extra revisions fetched per edition at most
REPLACES = 0.3  # word overlap from which a sentence born in an edit counts as the replacement of one it removed


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def first_change(probe: Callable[[int], bool | None], lo: int, hi: int, want: bool) -> int:
    """Smallest i in (lo, hi] with probe(i) == want, given probe(lo) != want and probe(hi) == want.
    probe may return None (hidden revision); such indexes are stepped over."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        val = None
        j = mid
        while j < hi:
            val = probe(j)
            if val is not None:
                break
            j += 1
        if val is None:  # everything from mid to hi-1 unknown: look left
            j = mid - 1
            while j > lo:
                val = probe(j)
                if val is not None:
                    break
                j -= 1
            if val is None:
                return hi
        if val == want:
            hi = j
        else:
            lo = j
    return hi


def first_lasting_change(
    probe: Callable[[int], bool | None], lo: int, hi: int, want: bool, hours: Callable[[int], float]
) -> int:
    """Like first_change, but a change undone within 24 hours does not count."""
    while True:
        k = first_change(probe, lo, hi, want)
        back = None
        j = k + 1
        while j <= hi and hours(j) - hours(k) < 24:
            if probe(j) is (not want):
                back = j
            j += 1
        if back is None:
            return k
        lo = back


@cache
def _revision(lang: str, rev_id: int) -> dict | None:
    """One revision with its text, in the shape of a snapshot record; None when the text is hidden."""
    body = wapi.get(
        wapi.api_url(lang),
        {
            "action": "query",
            "prop": "revisions",
            "revids": str(rev_id),
            "rvprop": "ids|timestamp|comment|sha1|content",
            "rvslots": "main",
            "formatversion": 2,
        },
    )
    pages = body["query"].get("pages") or []
    revs = pages[0].get("revisions", []) if pages else []
    text = revs[0].get("slots", {}).get("main", {}).get("content") if revs else None
    if text is None:
        return None
    r = revs[0]
    return {
        "rev_id": r["revid"],
        "ts": r["timestamp"],
        "comment": r.get("comment"),
        "sha1": r.get("sha1"),
        "text": text,
    }


@cache
def _parsed(lang: str, rev_id: int):
    rec = _revision(lang, rev_id)
    return None if rec is None else parse(rec["text"]).sentences


def _sentences(lang: str, rev_id: int) -> tuple[str, ...] | None:
    sents = _parsed(lang, rev_id)
    return None if sents is None else tuple(s["text"] for s in sents)


def _hashes(lang: str, rev_id: int) -> frozenset[str] | None:
    sents = _parsed(lang, rev_id)
    return None if sents is None else frozenset(s["h"] for s in sents)


def _matches(sents, rx: re.Pattern) -> bool | None:
    if sents is None:
        return None
    return any(rx.search(s) for s in sents)


def bisect_claim(topic: str, lang: str, regex: str) -> dict:
    rx = re.compile(regex)
    meta = meta_order(topic, lang)
    pos = {r["rev_id"]: i for i, r in enumerate(meta)}
    snaps = sorted(read_jsonl(hist_dir(topic) / f"{lang}.snap.jsonl.gz"), key=lambda r: r["ts"])
    snap_has = [(s["rev_id"], any(rx.search(x["text"]) for x in parse(s["text"]).sentences)) for s in snaps]
    hits = [i for i, (_, h) in enumerate(snap_has) if h]
    out = {"lang": lang, "regex": regex}
    if not hits:
        out["error"] = "no snapshot matches"
        return out

    def probe(i: int) -> bool | None:
        return _matches(_sentences(lang, meta[i]["rev_id"]), rx)

    def hours(i: int) -> float:
        return parse_ts(meta[i]["ts"]).timestamp() / 3600

    first, last = hits[0], hits[-1]
    if first > 0:
        lo, hi = pos[snap_has[first - 1][0]], pos[snap_has[first][0]]
        k = first_lasting_change(probe, lo, hi, want=True, hours=hours)
        out["first_with"] = {
            "rev_id": meta[k]["rev_id"],
            "ts": meta[k]["ts"],
            "comment": meta[k].get("comment"),
            "snapshot_rev": snap_has[first][0],
        }
    if last < len(snap_has) - 1:
        lo, hi = pos[snap_has[last][0]], pos[snap_has[last + 1][0]]
        k = first_lasting_change(probe, lo, hi, want=False, hours=hours)
        out["first_without"] = {
            "rev_id": meta[k]["rev_id"],
            "ts": meta[k]["ts"],
            "comment": meta[k].get("comment"),
            "snapshot_rev": snap_has[last + 1][0],
            "last_with_rev": meta[k - 1]["rev_id"],
        }
    return out


def gather(topic: str, lang: str, rs: list[dict], budget: int = MAX_EXTRA) -> tuple[list[dict], int]:
    """Extra revisions (with text) for one edition: the revision of every bisected edit and the one before it, then
    the same pair for each replacement of a claim (a sentence the edit wrote into the section the claim left) that is
    gone again by the next sample, followed down the chain of replacements until none is left or the budget of
    fetched revisions is spent. Returns (extra revisions, wordings chased)."""
    meta = meta_order(topic, lang)
    pos = {r["rev_id"]: i for i, r in enumerate(meta)}
    snap_ids = {r["rev_id"] for r in read_jsonl(hist_dir(topic) / f"{lang}.snap.jsonl.gz")}
    extra: dict[int, dict] = {}

    def add(i: int) -> bool:
        rid = meta[i]["rev_id"]
        if rid in snap_ids or rid in extra or len(extra) >= budget:
            return False
        rec = _revision(lang, rid)
        if rec is None:  # hidden revision: not a sample
            return False
        extra[rid] = rec
        return True

    for r in rs:
        for key in ("first_with", "first_without"):
            if e := r.get(key):
                k = pos[e["rev_id"]]
                add(k - 1)
                add(k)

    def hours(i: int) -> float:
        return parse_ts(meta[i]["ts"]).timestamp() / 3600

    claim_rx = [re.compile(r["regex"]) for r in rs]
    followed: set[str] = set()  # the claims and every wording that replaced one of them
    chased: set[tuple[str, int]] = set()
    for _ in range(MAX_ROUNDS):
        revs = samples(topic, lang, exact=False, extra=list(extra.values()))
        sp = [pos.get(r["rev_id"]) for r in revs]
        idx = {r["rev_id"]: i for i, r in enumerate(revs)}
        w, _cache = page_walk(topic, lang, exact=False, extra=list(extra.values()))
        spans = [
            (lv, idx[lv["born_rev"]], idx[lv["died_rev"]] if lv["died_rev"] is not None else None) for lv in w.lives
        ]
        followed |= {lv["h"] for lv, _b, _d in spans if any(rx.search(lv["text"]) for rx in claim_rx)}
        # a sentence an exact edit wrote in place of a followed sentence (the one that edit removed) is its
        # replacement: born at that sample and sharing enough words with it (sections are often renamed in the edit)
        died_at: dict[int, list[set[str]]] = {}
        for lv, _b, d in spans:
            if lv["h"] in followed and d is not None and revs[d]["adjacent"]:
                died_at.setdefault(d, []).append(_words(lv["text"]))
        added = False
        for lv, b, d in spans:
            if lv["h"] not in followed:
                if b not in died_at or not any(_jaccard(_words(lv["text"]), ws) >= REPLACES for ws in died_at[b]):
                    continue
            followed.add(lv["h"])
            if b not in died_at:
                continue
            transient = d == b + 1 and not revs[d]["adjacent"]
            if not transient or (lv["h"], b) in chased or sp[b] is None or sp[d] is None:
                continue
            chased.add((lv["h"], b))

            def probe(i: int, h=lv["h"]) -> bool | None:
                hs = _hashes(lang, meta[i]["rev_id"])
                return None if hs is None else h in hs

            k = first_lasting_change(probe, sp[b], sp[d], want=False, hours=hours)
            added |= add(k - 1)
            added |= add(k)
        if not added:
            break
    return sorted(extra.values(), key=lambda r: pos[r["rev_id"]]), len(chased)


def apply(topic: str, results: list[dict]) -> dict[str, dict]:
    """Rebuild the lives of every bisected edition over its snapshots plus the extra revisions around each edit.

    The yearly samples alone date every change to a snapshot; moving only the claim's own bounds (the old approach)
    left its replacement wording born at the next snapshot, so the edition said nothing in between (issue #30).
    Walking whole pages at the exact edit dates the claim's death and its replacement's birth to the same edit."""
    by_lang: dict[str, list[dict]] = {}
    for r in results:
        by_lang.setdefault(r["lang"], []).append(r)
    out = {}
    for lang, rs in by_lang.items():
        extra, chased = gather(topic, lang, rs)
        write_jsonl(extra_path(topic, lang), extra)
        w, _cache = page_walk(topic, lang, exact=False, extra=extra)
        write_jsonl(lives_dir() / f"{topic}-{lang}.jsonl.gz", w.lives)
        write_jsonl(lives_dir() / f"{topic}-{lang}.sections.jsonl.gz", w.sections)
        n_exact = sum(1 for lv in w.lives if lv["time_precision"] == "exact")
        out[lang] = {"extra_revisions": len(extra), "wordings_chased": chased, "lives": len(w.lives), "exact": n_exact}
    return out


def main(topic: str) -> None:
    claims = yaml.safe_load((ROOT / "pipeline" / "demo_claims.yaml").read_text(encoding="utf-8"))
    results = []
    for c in claims:
        if c["lang"] == "fi":
            results.append({**c, "note": "fi has every revision, lives are exact already"})
            continue
        r = bisect_claim(topic, c["lang"], c["regex"])
        results.append(r)
        fw, fb = r.get("first_without"), r.get("first_with")
        line = f"{c['lang']} {c['regex']!r}:"
        if fb:
            line += f" first_with={fb['rev_id']} {fb['ts']}"
        if fw:
            line += f" first_without={fw['rev_id']} {fw['ts']} comment={fw['comment']!r}"
        if not fb and not fw:
            line += " " + r.get("error", "present in every snapshot")
        print(line)
    rebuilt = apply(topic, [r for r in results if "regex" in r and "error" not in r and r["lang"] != "fi"])
    for lang, c in rebuilt.items():
        print(f"{lang} " + " ".join(f"{k}={v}" for k, v in c.items()))
    (lives_dir() / f"{topic}-bisect.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), "utf-8")
    print(wapi.stats_line())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    main(ap.parse_args().topic)
