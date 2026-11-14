import re

import yaml

from pipeline.checks import blocks
from pipeline.fetch import ROOT
from pipeline.load import batches


def test_batches_cut_by_rows():
    out = list(batches(((i,) for i in range(1201)), max_rows=500))
    assert [len(b) for b in out] == [500, 500, 201]


def test_batches_cut_by_bytes():
    rows = [("x" * 1000,)] * 10
    out = list(batches(rows, max_rows=500, max_bytes=3500))
    assert [len(b) for b in out] == [3, 3, 3, 1]


def test_one_huge_row_still_goes_alone():
    out = list(batches([("a",), ("x" * 10_000,), ("b",)], max_bytes=100))
    assert [len(b) for b in out] == [1, 1, 1]


def test_terms_compile_and_cover_every_edition():
    spec = yaml.safe_load((ROOT / "pipeline" / "terms.yaml").read_text(encoding="utf-8"))
    langs = set()
    for t in spec["terms"].values():
        for lang, pat in t.items():
            if lang != "gloss_en":
                re.compile(pat)
                langs.add(lang)
    assert langs == {"fi", "sv", "de", "en", "ru", "et", "uk"}


def test_checks_sql_blocks():
    names = [n for n, _ in blocks((ROOT / "pipeline" / "checks.sql").read_text(encoding="utf-8"))]
    assert "probe_en_2008_nearest" in names and "explain_ann_uses_emb" in names
    assert {"en_mainila_2009_10_after_bisect", "ru_mainila_2014_09_after_bisect", "term_hits_current_per_lang"} <= set(
        names
    )
    assert len(names) == len(set(names))


def _spec():
    return yaml.safe_load((ROOT / "pipeline" / "terms.yaml").read_text(encoding="utf-8"))


def _terms_in(lang, text):
    return {tid for tid, t in _spec()["terms"].items() if lang in t and re.search(t[lang], text, re.I)}


def test_term_stems_cover_inflected_et_and_uk_forms():
    # real sentences from the et and uk editions that the old patterns missed (issue #31)
    assert _terms_in("et", "Tegemist oli Nõukogude Liidu provokatsiooniga, mille korraldas luureosakond.") == {
        "provocation"
    }
    assert _terms_in("et", "Seepeale hakkas sõja provotseerimiseks N. Liidu eriteenistused tulistama.") == {
        "provocation"
    }
    assert _terms_in("uk", "Ці джерела підтверджують, що Майнільський інцидент був фальсифікацією.") == {"fabricated"}
    assert _terms_in("uk", "НКВС мав створити інсценуацію, що стала би приводом для війни.") == {"staged"}
    anchor = re.compile(_spec()["anchor"])
    for s in ["Mainila külas", "Mainilan laukaukset", "Майнільський інцидент", "у населённого пункта Майнила"]:
        assert anchor.search(s), s


def test_term_counts_in_the_sentence_after_the_anchor():
    from contract.engine import claim_hash
    from pipeline.load import anchored, near_anchor

    anchor = re.compile(_spec()["anchor"])
    lines = [
        "Soome valitsus lükkas pakkumise tagasi.",
        "Nõukogude Liidu valitsus teatas, et Soome tulistas Mainila külas punaväelasi.",
        "Tegemist oli Nõukogude provokatsiooniga.",
        "Üks.",
        "Kaks.",
        "Kolm.",
        "Neli on kaugel provokatsioonist.",
    ]
    secs = [{"text": "\n".join(lines), "row_start": "2014-01-01 00:00:00.000000", "row_end": None}]
    near = near_anchor(secs, anchor, window=3)

    def life(text, start="2015-01-01 00:00:00.000000", end=None):
        return {"h": claim_hash(text), "row_start": start, "row_end": end}

    assert anchored(life(lines[2]), near)  # next sentence after the anchor
    assert anchored(life(lines[0]), near)
    assert not anchored(life(lines[6]), near)  # five sentences away
    assert not anchored(life(lines[2], "2010-01-01 00:00:00.000000", "2013-01-01 00:00:00.000000"), near)  # no overlap
