import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from pipeline import atlas


def test_article_rows_join_titles_and_pack_vectors(tmp_path, monkeypatch):
    monkeypatch.setattr(atlas, "S", tmp_path)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"page_id": 1, "wikidata_id": "Q1", "title": "Talvisota"},
                {"page_id": 2, "wikidata_id": None, "title": "Ilman"},
            ]
        ),
        tmp_path / "articles-fi.parquet",
    )
    emb = pa.array([[0.5] * 1024, [1.0] * 1024, [2.0] * 1024], type=pa.list_(pa.float32(), 1024))
    pq.write_table(
        pa.table({"page_id": pa.array([1, 2, 3], pa.uint32()), "truncated": [False, True, False], "embedding": emb}),
        tmp_path / "vectors-bge-m3-fi.parquet",
    )
    rows = list(atlas.article_rows("fi"))
    assert [(r[1], r[2], r[3], r[4]) for r in rows] == [(1, "Q1", "Talvisota", 0), (2, "", "Ilman", 1)]
    assert np.allclose(np.frombuffer(rows[0][5], "<f4"), 0.5) and len(rows[0][5]) == 4096


def test_atlas_sql_shape():
    assert "VEC_DISTANCE_COSINE(f.emb, s.emb)" in atlas.ATLAS_SQL and "'all'" in atlas.ATLAS_SQL
