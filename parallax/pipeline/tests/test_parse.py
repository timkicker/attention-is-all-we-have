from pathlib import Path

import pytest

from contract.engine import claim_hash
from pipeline.parse import ParseCache, parse

DATA = Path(__file__).parent / "fixtures"


def texts(name: str) -> list[str]:
    return [s["text"] for s in parse((DATA / f"{name}.wiki").read_text(encoding="utf-8")).sentences]


def test_en_2008_staged():
    assert any("the Soviets staged the shelling of Mainila" in s for s in texts("en-2008"))


def test_ru_current_by_soviet_account():
    assert any("по заявлению советской стороны" in s for s in texts("ru-current"))


def test_fi_date_stays_in_one_sentence():
    hits = [s for s in texts("fi-current") if "12. maaliskuuta 1940" in s]
    assert hits and all(s.index("12. maaliskuuta 1940") > 10 for s in hits)


def test_fi_infobox_rows_with_casualties():
    p = parse((DATA / "fi-current.wiki").read_text(encoding="utf-8"))
    rows = [s["text"] for s in p.sentences if s["section"] == "[infobox]"]
    assert any(r.startswith("tappiot1: 25 904") for r in rows)
    assert p.infobox["nimi"] == "Talvisota"


@pytest.mark.parametrize(
    "name", ["en-2008", "ru-current", "fi-current", "de-current", "sv-current", "et-current", "uk-current"]
)
def test_no_markup_left(name):
    out = texts(name)
    assert out, name
    for s in out:
        for bad in ("{{", "}}", "[[", "]]", "|", "v t e", "<ref", "\x00"):
            assert bad not in s, (bad, s)
        assert len(s) >= 8


def test_markup_constructs():
    wiki = """{{Infobox military conflict
| conflict = Test War
| image = [[File:X.jpg|200px]]
| casualties1 = 10 dead<br/>20 wounded
}}
[[File:Map.png|thumb|A caption with [[link]] inside.]]
The '''Test War''' was fought in [[Finland|Finnish]] territory in {{convert|20|km}} stretches.<ref name="a" /> \
It ended in {{lang|fi|kevät}} 1940 after long talks.<ref>{{cite book|title=X}}</ref> Short.
{| class="wikitable"
| cell text that must vanish entirely from output
|}

== History ==
=== Early phase ===
Soviet forces crossed the border on 30 November 1939 at dawn.{{sfn|Trotter|2002|p=3}}
==== Detail ====
The detail sentence stays in the Early phase section here.
* A list item that is long enough to count as a sentence.
[[fi:Talvisota]]
[[Category:Wars]]
"""
    p = parse(wiki)
    by_text = {s["text"]: s for s in p.sentences}
    assert by_text["casualties1: 10 dead, 20 wounded"]["section"] == "[infobox]"
    assert "conflict: Test War" in by_text
    assert not any(k.startswith("image") for k in p.infobox)
    first = by_text["The Test War was fought in Finnish territory in 20 km stretches."]
    assert first["has_ref"] is True and first["section"] == "[lead]"
    glued = [t for t in by_text if t.startswith("It ended in kevät 1940")]
    assert glued and by_text[glued[0]]["has_ref"] is True
    assert by_text["Soviet forces crossed the border on 30 November 1939 at dawn."]["has_ref"] is True
    assert by_text["The detail sentence stays in the Early phase section here."]["section"] == "Early phase"
    assert "A list item that is long enough to count as a sentence." in by_text
    assert not any("cell text" in t or "caption" in t or "Talvisota" in t or "Wars" in t for t in by_text)
    assert all(s["h"] == claim_hash(s["text"]) for s in p.sentences)
    assert [s["idx"] for s in p.sentences] == list(range(len(p.sentences)))
    assert set(p.sections) == {"[infobox]", "[lead]", "Early phase"}


def test_duplicate_sentence_kept_once():
    p = parse("A sentence that appears twice in one page.\n\nA sentence that appears twice in one page.\n")
    assert len(p.sentences) == 1


def test_cache_parses_same_sha1_once():
    c = ParseCache()
    a = c.get("abc", "First version of the article text here.")
    b = c.get("abc", "ignored, the sha1 decides")
    c.get("def", "Second version of the article text here.")
    assert a is b and c.parsed == 2 and c.cache_hits == 1
