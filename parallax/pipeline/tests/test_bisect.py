from pipeline.bisect import first_change


def test_first_change_on_fake_history():
    # claim present in revs 0..6, gone from 7 on
    has = [True] * 7 + [False] * 13
    calls = []

    def probe(i):
        calls.append(i)
        return has[i]

    assert first_change(probe, 0, len(has) - 1, want=False) == 7
    assert len(calls) <= 6


def test_first_change_birth():
    has = [False] * 11 + [True] * 4
    assert first_change(lambda i: has[i], 0, len(has) - 1, want=True) == 11


def test_unknown_revision_is_skipped():
    has = [True, True, None, None, False, False]
    assert first_change(lambda i: has[i], 0, 5, want=False) == 4


def test_vandal_dip_is_skipped():
    from pipeline.bisect import first_lasting_change

    # gone at 3 for minutes (vandalism), back at 4, gone for good at 8
    has = [True, True, True, False, True, True, True, True, False, False]
    ts = [0, 10, 20, 30, 31, 50, 60, 70, 100, 200]  # hours
    out = first_lasting_change(lambda i: has[i], 0, 9, want=False, hours=lambda i: ts[i])
    assert out == 8


def test_replacement_is_linked_by_shared_words():
    from pipeline.bisect import REPLACES, _jaccard, _words

    old = _words("On 26 November, the Soviets staged the shelling of Mainila, an incident in which artillery shelled")
    new = _words("On 26 November, a border incident near the village of Mainila occurred.")
    other = _words("Called the Finnish Democratic Republic, it was headed by O. W. Kuusinen.")
    assert _jaccard(old, new) >= REPLACES
    assert _jaccard(old, other) < REPLACES
