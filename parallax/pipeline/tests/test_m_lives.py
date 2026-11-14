from datetime import datetime

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline import m_lives


def _toy(path):
    rows = []
    for pid, title in ((1, "A"), (2, "B"), (3, "C")):
        for k in range(3):
            rows.append(
                {
                    "page_id": pid,
                    "title": title,
                    "rev_id": pid * 10 + k,
                    "parent_id": None,
                    "timestamp": datetime(2010 + k, 1, 1),
                    "user": "SomeUser",
                    "anonymous": False,
                    "comment": "lähteetön väite poistettu" if k == 2 else "",
                    "minor": False,
                    "sha1": f"{pid}-{k}",
                    "bytes": 10,
                    "text": "Ensimmäinen virke on tarpeeksi pitkä tähän.\n\n"
                    + ("Toinen virke on myös pitkä tähän." if k < 2 else ""),
                }
            )
    pq.write_table(pa.Table.from_pylist(rows), path)


def test_reader_groups_pages_and_never_reads_user(tmp_path, monkeypatch):
    path = tmp_path / "versions-99.parquet"
    _toy(path)
    read_cols = []
    orig = pq.ParquetFile.iter_batches

    def spy(self, *a, **kw):
        read_cols.append(kw.get("columns"))
        return orig(self, *a, **kw)

    monkeypatch.setattr(pq.ParquetFile, "iter_batches", spy)
    pages = list(m_lives.pages_of(path))
    assert [p[0] for p in pages] == [1, 2, 3]
    assert all(len(rows) == 3 for _, _, rows in pages)
    assert read_cols and all("user" not in c and "anonymous" not in c for c in read_cols)
    assert all("user" not in r for _, _, rows in pages for r in rows)


def test_page_lives_and_reason(tmp_path):
    path = tmp_path / "versions-99.parquet"
    _toy(path)
    pid, title, rows = next(m_lives.pages_of(path))
    res = m_lives.page_lives(pid, title, rows)
    dead = [lv for lv in res["lives"] if lv["died_rev"]]
    assert len(res["lives"]) == 2 and len(dead) == 1
    assert dead[0]["reason"] == "unsourced" and dead[0]["died_rev"] == 12


def test_reason_rules():
    assert m_lives.reason("Korjaus: väärä vuosi") == "error"
    assert m_lives.reason("poistettu spekulaatio") == "speculation"
    assert m_lives.reason("kielenhuoltoa") == "other"
    assert m_lives.reason("") == "none" and m_lives.reason(None) == "none"
