"""Cut contract/fixtures/seed-mini.sql from the Saturday spike database (schema `lens`).

Run once by the contract owner: `uv run python scripts/build_seed_mini.py SPIKE_DIR`.
SPIKE_DIR holds the spike's out/ and raw/ folders (snapshot revisions and page ids).
The spike database is read through SPIKE_HOST, SPIKE_PORT, SPIKE_USER, SPIKE_PASSWORD.
Output: claims (with vectors), sections, pages, revisions, plus verdicts and glosses
from contract/fixtures/engine. No user names exist in any input.
"""

import json
import os
import re
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from contract.engine import FIXTURES, claim_hash  # noqa: E402

TOPIC, WIKIDATA, LABEL = "winterwar", "Q134949", "Winter War"
MAX_TS = "2106-02-07 06:28:15.999999"
# Sections around Mainila and the casualty figures, per edition.
SECTIONS = {
    "fi": ["Propagandahyökkäys sodan aattopäivinä", "Sodan alku", "Osapuolten tappiot"],
    "sv": ["Skotten i Mainila", "Bakgrund"],
    "de": ["Verhandlungen mit Finnland und Kriegsbeginn", "Kriegsopfer"],
    "en": ["Background", "Shelling of Mainila", "Shelling of Mainila and Soviet intentions", "The shelling of Mainila"],
    "ru": ["Майнильский инцидент", "Повод к войне и разрыв отношений", "Потери Финляндии"],
    "et": ["Sõja algus", "Kaotused"],
}
MENTION = re.compile(r"mainil|майнил|26[\s,.]?662|25[\s,.]?904|22[\s,.]?830", re.I)
# Demo revisions outside the snapshots (PLAN section 0), comments as published on Wikipedia.
EXTRA_REVS = {
    ("en", 309285088): "rewrote the mainila incident part to correspond with the article",
    ("ru", 64106894): None,
    ("ru", 63917953): None,
}


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    s = str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")
    return f"'{s}'"


def main(spike: Path) -> None:
    snaps = json.loads((spike / "out/snapshots.json").read_text())
    cur = json.loads((spike / "out/current-winterwar.json").read_text())
    meta = json.loads((spike / "raw/revmeta-winterwar.json").read_text())
    langs = list(SECTIONS)
    page_id = {lang: meta[lang]["pageid"] for lang in langs}
    titles = {lang: meta[lang]["title"] for lang in langs}
    rev_at: dict[tuple[str, str], int] = {}
    for s in snaps:
        rev_at[(s["lang"], s["rev_ts"].replace("T", " ").replace("Z", ""))] = s["rev"]
    for lang in langs:
        rev_at[(lang, cur[lang]["ts"].replace("T", " ").replace("Z", ""))] = cur[lang]["rev"]
    revs_meta = {}
    for lang in langs:
        for r in json.loads((spike / f"raw/revs-winterwar-{lang}.json").read_text()):
            revs_meta[(lang, r["revid"])] = r

    db = pymysql.connect(
        host=os.environ.get("SPIKE_HOST", "127.0.0.1"),
        port=int(os.environ.get("SPIKE_PORT", "3399")),
        user=os.environ.get("SPIKE_USER", "root"),
        password=os.environ["SPIKE_PASSWORD"],
        database="lens",
        charset="utf8mb4",
    )
    c = db.cursor()
    c.execute("SET time_zone='+00:00'")
    c.execute(
        "SELECT lang, section, text, emb, row_start, row_end FROM sentence FOR SYSTEM_TIME ALL"
        " WHERE topic=%s ORDER BY lang, row_start",
        (TOPIC,),
    )
    claims = []
    for lang, section, text, emb, rs, re_ in c.fetchall():
        if lang in SECTIONS and (section in SECTIONS[lang] or MENTION.search(text)):
            claims.append((lang, section, text, emb, str(rs), str(re_)))
    c.execute(
        "SELECT lang, section, rev_id, n_sent, text, row_start, row_end FROM section_text FOR SYSTEM_TIME ALL"
        " WHERE topic=%s ORDER BY lang, row_start",
        (TOPIC,),
    )
    wanted = {(lang, s) for lang, secs in SECTIONS.items() for s in secs}
    sections = [r for r in c.fetchall() if (r[0], r[1]) in wanted]

    out = [
        "-- Parallax seed-mini: Winter War rows around Mainila and the casualty figures, 6 editions.",
        "-- Built by scripts/build_seed_mini.py from the spike database. Load after contract/schema.sql.",
        "SET time_zone='+00:00';",
        "SET system_versioning_insert_history=1;",
        f"INSERT INTO topic VALUES ({q(TOPIC)},{q(WIKIDATA)},{q(LABEL)},'deep');",
    ]
    for lang in langs:
        out.append(f"INSERT INTO page VALUES ({q(lang)},{page_id[lang]},{q(TOPIC)},{q(titles[lang])},'api','yearly');")
    revs = {(lang, rev): None for (lang, _), rev in rev_at.items()} | EXTRA_REVS
    for (lang, rev), comment in sorted(revs.items()):
        r = revs_meta.get((lang, rev), {})
        ts = r.get("timestamp", "").replace("T", " ").replace("Z", "") or None
        if ts is None:
            ts = next(t for (lg, t), rv in rev_at.items() if lg == lang and rv == rev)
        snap = 1 if (lang, rev) in {(lg, rv) for (lg, _), rv in rev_at.items()} else 0
        out.append(
            "INSERT INTO revision VALUES ("
            f"{q(lang)},{rev},{page_id[lang]},{q(r.get('parentid') or None)},{q(ts)},{q(r.get('size'))},"
            f"{1 if r.get('minor') else 0},{q(comment)},{snap});"
        )
    for lang, section, rev_id, n_sent, text, rs, re_ in sections:
        out.append(
            "INSERT INTO section_text (topic_id,lang,section,rev_id,n_sent,text,row_start,row_end) VALUES ("
            f"{q(TOPIC)},{q(lang)},{q(section)},{rev_id},{n_sent or 0},{q(text)},{q(str(rs))},{q(str(re_))});"
        )
    seen = set()
    for lang, section, text, emb, rs, re_ in claims:
        h = claim_hash(text)
        if (lang, h, re_) in seen:  # same text twice in one snapshot
            continue
        seen.add((lang, h, re_))
        born = rev_at[(lang, rs)]
        died = None if re_.startswith("2106") else rev_at[(lang, re_)]
        b64 = __import__("base64").b64encode(emb).decode()
        out.append(
            "INSERT INTO claim (lang,page_id,h,topic_id,section,text,born_rev,died_rev,died_comment,time_precision,"
            "has_ref,had_ref,emb,row_start,row_end) VALUES ("
            f"{q(lang)},{page_id[lang]},{q(h)},{q(TOPIC)},{q(section)},{q(text)},{born},{q(died)},NULL,'snapshot',"
            f"0,0,FROM_BASE64('{b64}'),{q(rs)},{q(re_)});"
        )
    judge = json.loads((FIXTURES / "judge.json").read_text())
    hashes = {(lang, h) for lang, h, _ in seen}
    for key, v in judge.items():
        if (v["a_lang"], key.split(":")[0]) not in hashes:
            continue  # pairs from the recorded answer, not between two claim rows
        out.append(
            "INSERT INTO verdict VALUES ("
            f"{q(v['a_lang'])},{q(key.split(':')[0])},{q(v['b_lang'])},{q(key.split(':')[1])},'judge-v1',"
            f"{q(v['label'])},{q(json.dumps(v.get('numbers', []), ensure_ascii=False))},"
            f"{q(json.dumps(v.get('terms', []), ensure_ascii=False))},'fake-judge',NULL,'2026-11-14 15:00:00');"
        )
    gloss = json.loads((FIXTURES / "gloss.json").read_text())
    for key, v in gloss.items():
        lang, h = key.split(":")
        out.append(f"INSERT INTO gloss VALUES ({q(lang)},{q(h)},{q(v['text_en'])},'fixture-gloss');")
    path = ROOT / "contract/fixtures/seed-mini.sql"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(seen)} claims, {len(sections)} sections, {path.stat().st_size} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
