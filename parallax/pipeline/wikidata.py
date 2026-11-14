"""Find an article by name and read its Wikidata item: the qid, the English title and description, and the title
in each of the seven editions. Every request goes through the polite client (pipeline.wapi), so it is cached on disk.
"""

import re

from pipeline import wapi

LANGS = ("fi", "sv", "de", "en", "ru", "et", "uk")
WIKIDATA = "https://www.wikidata.org/w/api.php"
QID = re.compile(r"^Q[1-9][0-9]*$")
MAX_RESULTS = 6


def _pages(lang: str, q: str, generator: str) -> list[dict]:
    """Pages of one wiki for a search, in result order, with qid, description and length."""
    params = {
        "action": "query",
        "formatversion": 2,
        "generator": generator,
        "prop": "pageprops|description|info",
        "ppprop": "wikibase_item|disambiguation",
        "redirects": 1,
    }
    if generator == "prefixsearch":
        params |= {"gpssearch": q, "gpslimit": MAX_RESULTS * 2, "gpsnamespace": 0}
    else:
        params |= {"gsrsearch": q, "gsrlimit": MAX_RESULTS * 2, "gsrnamespace": 0}
    body = wapi.get(wapi.api_url(lang), params, max_age_s=0, interactive=True)  # typed by a visitor: not kept
    pages = body.get("query", {}).get("pages", [])
    pages = [p for p in pages if "missing" not in p and "disambiguation" not in p.get("pageprops", {})]
    return sorted(pages, key=lambda p: p.get("index", 0))


def entities(qids: list[str]) -> dict[str, dict]:
    """qid -> {label_en, description, titles: {lang: title}} for the seven editions (one request per 50 ids)."""
    out: dict[str, dict] = {}
    for i in range(0, len(qids), 50):
        chunk = qids[i : i + 50]
        body = wapi.get(
            WIKIDATA,
            {
                "action": "wbgetentities",
                "ids": "|".join(chunk),
                "props": "labels|descriptions|sitelinks",
                "languages": "en",
                "sitefilter": "|".join(f"{lang}wiki" for lang in LANGS),
            },
            max_age_s=0,  # asked while a visitor waits (search, a new ingest); sitelinks change, so never kept
            interactive=True,
        )
        for qid, ent in (body.get("entities") or {}).items():
            if "missing" in ent:
                continue
            links = ent.get("sitelinks") or {}
            out[qid] = {
                "qid": qid,
                "label_en": (ent.get("labels", {}).get("en") or {}).get("value"),
                "description": (ent.get("descriptions", {}).get("en") or {}).get("value"),
                "titles": {lang: links[f"{lang}wiki"]["title"] for lang in LANGS if f"{lang}wiki" in links},
            }
    return out


def entity(qid: str) -> dict | None:
    return entities([qid]).get(qid)


def search(q: str) -> list[dict]:
    """Up to six articles for a search string: English prefix search, else full-text search, else the same in
    Finnish (so "Talvisota" finds the Winter War). A qid typed as is resolves directly.

    Each result: {qid, title, description, titles, en_length}. title is the English title (else the Wikidata label,
    else the Finnish title); en_length is the English article's size in bytes or None."""
    q = q.strip()
    if not q:
        return []
    found: list[tuple[str, dict]] = []
    if QID.match(q.upper()):
        found = [(q.upper(), {})]
    else:
        for lang, gen in (("en", "prefixsearch"), ("en", "search"), ("fi", "prefixsearch"), ("fi", "search")):
            pages = [p for p in _pages(lang, q, gen) if p.get("pageprops", {}).get("wikibase_item")]
            if pages:
                found = [(p["pageprops"]["wikibase_item"], p | {"lang": lang}) for p in pages]
                break
    seen: dict[str, dict] = {}
    for qid, p in found:
        seen.setdefault(qid, p)
    qids = list(seen)[:MAX_RESULTS]
    ents = entities(qids) if qids else {}
    out = []
    for qid in qids:
        ent = ents.get(qid)
        if not ent:
            continue
        p = seen[qid]
        en_page = p if p.get("lang") == "en" else {}
        title = ent["titles"].get("en") or ent["label_en"] or ent["titles"].get("fi") or qid
        out.append(
            {
                "qid": qid,
                "title": title,
                "description": ent["description"] or (en_page.get("description") if en_page else None),
                "titles": ent["titles"],
                "en_length": en_page.get("length") if en_page else None,
            }
        )
    return out
