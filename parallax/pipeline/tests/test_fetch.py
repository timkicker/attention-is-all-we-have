from pipeline import fetch


def _meta(*pairs):
    return [{"rev_id": r, "ts": ts} for r, ts in pairs]


def test_snapshots_one_per_new_year_plus_current():
    meta = _meta(
        (1, "2005-03-01T00:00:00Z"),
        (2, "2005-12-31T23:59:59Z"),
        (3, "2006-01-01T00:00:00Z"),  # exactly at midnight: belongs to 2006, not before it
        (4, "2006-07-01T00:00:00Z"),
        (5, "2008-02-01T00:00:00Z"),
    )
    snaps = fetch.pick_snapshots(meta, last_year=2009)
    # 2006-01-01 -> rev 2, 2007-01-01 -> rev 4, 2008-01-01 -> rev 4 (deduped), 2009-01-01 -> rev 5, current 5
    assert snaps == [2, 4, 5]


def test_snapshots_single_revision():
    assert fetch.pick_snapshots(_meta((7, "2020-05-05T00:00:00Z")), last_year=2026) == [7]


def test_meta_row_never_has_user():
    rev = {
        "revid": 9,
        "parentid": 8,
        "timestamp": "2010-01-01T00:00:00Z",
        "size": 10,
        "sha1": "ab",
        "comment": "c",
        "minor": True,
        "user": "Someone",
    }
    row = fetch.meta_row(rev)
    assert "user" not in row and row["rev_id"] == 9 and row["minor"] == 1 and row["sha1"] == "ab"
