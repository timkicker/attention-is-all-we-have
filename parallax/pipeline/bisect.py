"""A5: the exact edit, date and comment for every claim the demo shows changing.

Lives of the six API editions have yearly snapshot bounds. For each (lang, regex) in demo_claims.yaml we binary
search the revision metadata between two snapshots, fetching single revisions (cached), and replace the snapshot
bounds of that life with the exact revision, time and comment. A disappearance that is undone within 24 hours
(vandalism, PLAN noise rule) is skipped and the search continues after it.
"""

import argparse
import json
import re
from collections.abc import Callable
from functools import cache

import yaml

from pipeline import wapi
from pipeline.fetch import ROOT, hist_dir, read_jsonl, write_jsonl
from pipeline.lives import fmt, lives_dir, parse_ts
from pipeline.parse import parse


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
def _sentences(lang: str, rev_id: int) -> tuple[str, ...] | None:
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
    return tuple(s["text"] for s in parse(text).sentences)


def _matches(sents, rx: re.Pattern) -> bool | None:
    if sents is None:
        return None
    return any(rx.search(s) for s in sents)


def bisect_claim(topic: str, lang: str, regex: str) -> dict:
    rx = re.compile(regex)
    meta = sorted(read_jsonl(hist_dir(topic) / f"{lang}.meta.jsonl.gz"), key=lambda r: r["ts"])
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


def apply(topic: str, results: list[dict]) -> int:
    """Rewrite the matching lives' snapshot bounds with the exact edits. Returns lives changed."""
    changed = 0
    by_lang: dict[str, list[dict]] = {}
    for r in results:
        by_lang.setdefault(r["lang"], []).append(r)
    for lang, rs in by_lang.items():
        path = lives_dir() / f"{topic}-{lang}.jsonl.gz"
        lives = list(read_jsonl(path))
        for r in rs:
            rx = re.compile(r["regex"])
            if fw := r.get("first_without"):
                for lv in lives:
                    if lv["died_rev"] == fw["snapshot_rev"] and rx.search(lv["text"]):
                        lv.update(
                            died_rev=fw["rev_id"],
                            row_end=fmt(parse_ts(fw["ts"])),
                            died_comment=fw["comment"] or None,
                            time_precision="exact",
                        )
                        changed += 1
            if fb := r.get("first_with"):
                for lv in lives:
                    if lv["born_rev"] == fb["snapshot_rev"] and rx.search(lv["text"]):
                        lv.update(born_rev=fb["rev_id"], row_start=fmt(parse_ts(fb["ts"])))
                        if lv["died_rev"] is None or lv["time_precision"] == "exact":
                            lv["time_precision"] = "exact"
                        changed += 1
        write_jsonl(path, lives)
    return changed


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
    n = apply(topic, [r for r in results if "regex" in r and "error" not in r and r["lang"] != "fi"])
    (lives_dir() / f"{topic}-bisect.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), "utf-8")
    print(f"lives updated: {n}  {wapi.stats_line()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    main(ap.parse_args().topic)
