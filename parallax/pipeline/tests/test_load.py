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
    assert len(names) == len(set(names))
