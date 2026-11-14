"""A3: one wikitext parser for M and API revisions, so hashes agree within an edition.

parse(text) -> Parsed(sentences=[{section, idx, text, h, has_ref}], sections={name: text}, infobox={k: v})

Fast path: nested {{templates}}, [[links]] and {|tables|} are found by scanning regex tokens, not characters,
so a 150 kB revision parses in tens of milliseconds. The first infobox template becomes key/value pairs.
A per-page cache keyed by revision sha1 (ParseCache) makes reverts free.
"""

import re
from dataclasses import dataclass, field

from contract.engine import claim_hash, split_sentences

REF_MARK = "\x00"
INFOBOX_NAMES = re.compile(
    r"infobox|tietolaatikko|taistelu|sota\b|карточка|картка|конфликт|faktamall|infokast|sõjaline konflikt", re.I
)
KEEP_LAST = re.compile(r"^(lang(-[a-z-]+)?|lang\s*\|.*|transl|transliteration|nobr)$", re.I)
KEEP_FIRST = re.compile(r"^(nowrap|formatnum|nts|abbr|small|sub|sup|nobold|noitalic|ill|интервики)$", re.I)
REF_TEMPLATES = re.compile(r"^(sfn[a-z]*|efn[a-z]*|harvnb|harvtxt|rp|refn|r|cite note|примечание|sfn)$", re.I)
SPACE_TEMPLATES = re.compile(r"^(nbsp|spaces|space|·|dot|-)$", re.I)
DROP_TAGS = re.compile(
    r"<(gallery|math|timeline|imagemap|score|graph|mapframe|maplink|syntaxhighlight|templatestyles|chem)\b"
    r"[^>]*?(/>|>.*?</\1\s*>)",
    re.I | re.S,
)
COMMENT = re.compile(r"<!--.*?(-->|$)", re.S)
REF_SELF = re.compile(r"<ref\b[^>]*/\s*>", re.I)
REF_FULL = re.compile(r"<ref\b(?:[^>/]|/(?!\s*>))*>.*?</ref\s*>", re.I | re.S)
REF_OPEN = re.compile(r"<ref\b(?:[^>/]|/(?!\s*>))*>.*$", re.I | re.S)
REFERENCES = re.compile(r"<references\b[^>]*?(/>|>.*?</references\s*>)", re.I | re.S)
TEMPLATE_TOK = re.compile(r"\{\{|\}\}")
LINK_TOK = re.compile(r"\[\[|\]\]")
TABLE_OPEN = re.compile(r"^[ \t:]*\{\|", re.M)
TABLE_TOK = re.compile(r"^[ \t:]*(\{\||\|\})", re.M)
EXT_LINK = re.compile(r"\[(?:https?:)?//[^\s\]]+(?:\s+([^\]]*))?\]")
BARE_URL = re.compile(r"https?://\S+")
HTML_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*\b[^>]*?/?>")
BOLD_ITALIC = re.compile(r"'{2,5}")
HEADING = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.M)
DROP_NS = re.compile(
    r"^\s*:?\s*(file|image|media|category|tiedosto|kuva|luokka|fil|bild|kategori|datei|kategorie|файл|изображение|"
    r"категория|категорія|зображення|pilt|kategooria|meedia|mall|template|malline|шаблон|vorlage|wikt|"
    r"[a-z]{2,3}(-[a-z]{2,8})?)\s*:",
    re.I,
)
ENTITY = {"&nbsp;": " ", "&ndash;": "–", "&mdash;": "—", "&amp;": "&", "&minus;": "−", "&thinsp;": " ", "&#160;": " "}
ENTITY_RE = re.compile("|".join(map(re.escape, ENTITY)))
EMPTY_PARENS = re.compile(r"\(\s*[,;:]?\s*\)")
SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")
WS = re.compile(r"[ \t ]+")
INFOBOX_SKIP_KEYS = re.compile(
    r"image|kuva|bild|изображение|зображення|map|kartta|karta|width|size|pilt|caption_?map", re.I
)


def _spans(text: str, tok: re.Pattern, opener: str) -> list[tuple[int, int]]:
    """Top-level (start, end) spans of nested open/close tokens."""
    spans, depth, start = [], 0, 0
    for m in tok.finditer(text):
        if m.group(0).strip(" \t:").startswith(opener) or m.group(0) == opener:
            if depth == 0:
                start = m.start()
            depth += 1
        elif depth:
            depth -= 1
            if depth == 0:
                spans.append((start, m.end()))
    if depth:  # unclosed: runs to the end
        spans.append((start, len(text)))
    return spans


def _split_args(inner: str) -> list[str]:
    """Split a template body on top-level pipes (pipes inside nested {{ }} or [[ ]] stay)."""
    parts, depth, cur = [], 0, []
    i = 0
    n = len(inner)
    while i < n:
        two = inner[i : i + 2]
        if two in ("{{", "[["):
            depth += 1
            cur.append(two)
            i += 2
            continue
        if two in ("}}", "]]") and depth:
            depth -= 1
            cur.append(two)
            i += 2
            continue
        ch = inner[i]
        if ch == "|" and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


@dataclass
class _State:
    infobox_raw: str | None = None


def _templates(text: str, st: _State) -> str:
    out, last = [], 0
    for a, b in _spans(text, TEMPLATE_TOK, "{{"):
        out.append(text[last:a])
        last = b
        inner = text[a + 2 : b - 2] if text[b - 2 : b] == "}}" else text[a + 2 :]
        name_end = inner.find("|")
        name = (inner if name_end < 0 else inner[:name_end]).strip().replace("_", " ")
        lname = name.lower()
        if st.infobox_raw is None and INFOBOX_NAMES.search(lname):
            st.infobox_raw = text[a:b]
            continue
        if REF_TEMPLATES.match(lname):
            out.append(REF_MARK)
            continue
        if SPACE_TEMPLATES.match(lname):
            out.append(" ")
            continue
        if "{{" not in inner and "|" not in inner and not KEEP_FIRST.match(lname):
            continue  # {{Citation needed}}, {{clear}} and the like
        args = [x for x in _split_args(inner)[1:] if "=" not in x.split("[[")[0].split("{{")[0]]
        if lname == "convert" and args:
            out.append(" ".join(_templates(x, st).strip() for x in args[:2]))
        elif KEEP_LAST.match(lname) and args:
            out.append(_templates(args[-1], st))
        elif KEEP_FIRST.match(lname) and args:
            out.append(_templates(args[0], st))
        # every other template is dropped (navboxes, sidebars, citations, maps)
    out.append(text[last:])
    return "".join(out)


def _links(text: str) -> str:
    out, last = [], 0
    for a, b in _spans(text, LINK_TOK, "[["):
        out.append(text[last:a])
        last = b
        inner = text[a + 2 : b - 2] if text[b - 2 : b] == "]]" else text[a + 2 :]
        if DROP_NS.match(inner) and not inner.lstrip().startswith(":"):
            continue
        if "[[" in inner:
            inner = _links(inner)
        label = inner.rsplit("|", 1)[-1] if "|" in inner else inner.lstrip(":")
        if "|" not in inner and DROP_NS.match(inner):
            label = inner.split(":", 2)[-1]
        out.append(label)
    out.append(text[last:])
    return "".join(out)


def _tables(text: str) -> str:
    if not TABLE_OPEN.search(text):
        return text
    out, last = [], 0
    for a, b in _spans(text, TABLE_TOK, "{|"):
        out.append(text[last:a])
        last = b
    out.append(text[last:])
    return "".join(out)


def clean_inline(text: str, st: _State | None = None) -> str:
    """Wikitext of one block to plain text with REF_MARK where a reference was."""
    st = st or _State()
    text = REFERENCES.sub("", text)
    text = REF_SELF.sub(REF_MARK, text)
    text = REF_FULL.sub(REF_MARK, text)
    text = REF_OPEN.sub(REF_MARK, text)
    text = _templates(text, st)
    text = _tables(text)
    text = _links(text)
    text = EXT_LINK.sub(lambda m: m.group(1) or "", text)
    text = BARE_URL.sub("", text)
    text = HTML_TAG.sub("", text)
    text = BOLD_ITALIC.sub("", text)
    text = ENTITY_RE.sub(lambda m: ENTITY[m.group(0)], text)
    return text


def _finish(s: str) -> str:
    s = s.replace(REF_MARK, "")
    s = EMPTY_PARENS.sub("", s)
    s = WS.sub(" ", s)
    s = SPACE_BEFORE_PUNCT.sub(r"\1", s)
    return s.strip()


_REF_AFTER_PUNCT = re.compile(r"([.!?])((?:\s*" + REF_MARK + r")+)")


def _sentences(block: str) -> list[tuple[str, bool]]:
    block = _REF_AFTER_PUNCT.sub(lambda m: REF_MARK + m.group(1), block)
    out = []
    for s in split_sentences(WS.sub(" ", block)):
        has_ref = REF_MARK in s
        s = _finish(s)
        if len(s) >= 20 and not any(x in s for x in ("{{", "}}", "[[", "]]", "|")):
            out.append((s, has_ref))
    return out


def _infobox(raw: str) -> dict[str, str]:
    inner = raw[2:-2] if raw.endswith("}}") else raw[2:]
    out = {}
    for arg in _split_args(inner)[1:]:
        if "=" not in arg:
            continue
        key, raw_val = arg.split("=", 1)
        key = key.strip()
        if not key or key.isdigit() or INFOBOX_SKIP_KEYS.search(key):
            continue
        raw_val = re.sub(r"<br\s*/?>", ", ", raw_val, flags=re.I)
        raw_val = re.sub(r"\n\s*[*#]\s*", ", ", raw_val)
        val = _finish(clean_inline(raw_val))
        val = re.sub(r"\s*,\s*(,\s*)+", ", ", val).strip(" ,;")
        if val and not any(x in val for x in ("{{", "}}", "[[", "]]", "|")):
            out[key] = val
    return out


@dataclass
class Parsed:
    sentences: list[dict] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    infobox: dict[str, str] = field(default_factory=dict)


LIST_PREFIX = re.compile(r"^[*#:;]+\s*")


def parse(text: str) -> Parsed:
    text = COMMENT.sub("", text)
    text = DROP_TAGS.sub("", text)
    st = _State()
    # Templates first over the whole page (they span lines), then headings split the rest into sections.
    body = REFERENCES.sub("", text)
    body = REF_SELF.sub(REF_MARK, body)
    body = REF_FULL.sub(REF_MARK, body)
    body = _templates(body, st)
    body = _tables(body)
    out = Parsed()
    if st.infobox_raw:
        out.infobox = _infobox(st.infobox_raw)

    seen: set[str] = set()
    idx = 0

    def add(section: str, s: str, has_ref: bool) -> None:
        nonlocal idx
        h = claim_hash(s)
        if h in seen:
            return
        seen.add(h)
        out.sentences.append({"section": section, "idx": idx, "text": s, "h": h, "has_ref": has_ref})
        out.sections.setdefault(section, [])
        out.sections[section].append(s)
        idx += 1

    for k, v in out.infobox.items():
        s = f"{k}: {v}"
        if len(s) >= 8:
            add("[infobox]", s, False)

    pos, section = 0, "[lead]"
    chunks: list[tuple[str, str]] = []
    for m in HEADING.finditer(body):
        chunks.append((section, body[pos : m.start()]))
        level = len(m.group(1))
        if level <= 3:
            section = _finish(clean_inline(m.group(2)))[:255] or section
        pos = m.end()
    chunks.append((section, body[pos:]))

    for sec, chunk in chunks:
        chunk = REF_OPEN.sub(REF_MARK, chunk)
        chunk = _links(chunk)
        chunk = EXT_LINK.sub(lambda m: m.group(1) or "", chunk)
        chunk = BARE_URL.sub("", chunk)
        chunk = HTML_TAG.sub("", chunk)
        chunk = BOLD_ITALIC.sub("", chunk)
        chunk = ENTITY_RE.sub(lambda m: ENTITY[m.group(0)], chunk)
        # paragraphs: blank lines and list items are separate blocks
        block: list[str] = []
        for line in chunk.split("\n"):
            stripped = line.strip()
            if not stripped or LIST_PREFIX.match(stripped) or stripped.startswith(("|", "!", "__")):
                if block:
                    for s, r in _sentences(" ".join(block)):
                        add(sec, s, r)
                    block = []
                if stripped and LIST_PREFIX.match(stripped):
                    for s, r in _sentences(LIST_PREFIX.sub("", stripped)):
                        add(sec, s, r)
                continue
            block.append(stripped)
        if block:
            for s, r in _sentences(" ".join(block)):
                add(sec, s, r)

    out.sections = {k: "\n".join(v) for k, v in out.sections.items()}
    return out


class ParseCache:
    """Per-page cache keyed by revision sha1: a revert reuses the parse of the text it restores."""

    def __init__(self) -> None:
        self._by_sha1: dict[str, Parsed] = {}
        self.parsed = 0
        self.cache_hits = 0

    def get(self, sha1: str | None, text: str) -> Parsed:
        if sha1 and sha1 in self._by_sha1:
            self.cache_hits += 1
            return self._by_sha1[sha1]
        p = parse(text)
        self.parsed += 1
        if sha1:
            self._by_sha1[sha1] = p
        return p


def revisions(topic: str, lang: str):
    """Revisions with text of one edition in time order: every revision for fi, snapshots for the others."""
    from pipeline.fetch import hist_dir, read_jsonl

    d = hist_dir(topic)
    path = d / f"{lang}.every.jsonl.gz"
    if not path.exists():
        path = d / f"{lang}.snap.jsonl.gz"
    return sorted(read_jsonl(path), key=lambda r: r["ts"])


def main(topic: str) -> None:
    import json
    import time

    from pipeline.fetch import hist_dir

    pages = json.loads((hist_dir(topic) / "pages.json").read_text(encoding="utf-8"))
    print(f"{'lang':5} {'revs':>5} {'parsed':>6} {'hits':>5} {'now':>5} {'sec':>6}")
    for lang in pages:
        t = time.time()
        cache = ParseCache()
        last = None
        revs = revisions(topic, lang)
        for r in revs:
            last = cache.get(r.get("sha1"), r["text"])
        n_now = len(last.sentences) if last else 0
        print(f"{lang:5} {len(revs):5} {cache.parsed:6} {cache.cache_hits:5} {n_now:5} {time.time() - t:6.1f}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    main(ap.parse_args().topic)
