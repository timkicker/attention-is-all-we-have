from pipeline.sources import isbn_group, ref_counts, yearly


def test_isbn_groups():
    assert isbn_group("978-951-0-12345-6") == "FI"
    assert isbn_group("952-5026-12-3") == "FI"
    assert isbn_group("978-91-7353-123-4") == "SE"
    assert isbn_group("978-9985-3-1234-5") == "EE"
    assert isbn_group("978-5-17-012345-6") == "RU/USSR"
    assert isbn_group("979-10-90636-07-1") == "FR"
    assert isbn_group("0-7146-5203-2") == "EN"
    assert isbn_group("12345") is None


def test_ref_counts():
    text = (
        'Fact.<ref>{{kirjaviite|isbn=978-951-1-23456-7}}</ref> Other.<ref name="a"/> '
        "Third.<ref>[https://www.example.fi/x Page] ISBN 0-7146-5203-2</ref> "
        "[https://fi.wikipedia.org/wiki/X] {{cite|isbn = 978-951-1-23456-7}}"
    )
    c = ref_counts(text)
    assert c["refs"] == 3
    assert c["isbn"] == {"FI": 1, "EN": 1}  # the same ISBN twice counts once
    assert c["domains"] == {"example.fi": 1}


def test_yearly_snapshots():
    revs = [
        {"rev_id": i, "ts": ts}
        for i, ts in enumerate(
            ["2004-05-01T00:00:00Z", "2004-12-01T00:00:00Z", "2006-03-01T00:00:00Z", "2006-04-01T00:00:00Z"]
        )
    ]
    assert [r["rev_id"] for r in yearly(revs)] == [1, 3]
