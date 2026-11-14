from pipeline.bench import fmt_n, pct, recall


def test_percentiles():
    xs = list(range(1, 101))
    assert pct(xs, 0.5) == 51 and pct(xs, 0.95) == 96 and pct([], 0.5) == 0.0


def test_recall():
    assert recall(["a", "b", "c", "d"], ["a", "c", "x", "y"]) == 0.5
    assert recall([], []) == 0.0


def test_fmt_n():
    assert fmt_n(1118463) == "1 118 463" and fmt_n(None) == "None"
