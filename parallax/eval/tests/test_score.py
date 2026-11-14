from eval.score import agreement, judge_report, kappa, recall_at


def test_kappa_perfect_and_chance():
    assert kappa([("same", "same"), ("different", "different")]) == 1.0
    # always predicting one label on a balanced set gives kappa 0
    assert kappa([("same", "same"), ("different", "same")]) == 0.0
    assert kappa([]) is None


def test_kappa_known_value():
    # 2x2: 20 agree yes, 15 agree no, 5 + 10 disagree -> po 0.7, pe 0.5 -> 0.4
    pairs = [("a", "a")] * 20 + [("b", "b")] * 15 + [("a", "b")] * 5 + [("b", "a")] * 10
    assert kappa(pairs) == 0.4


def test_agreement_and_report_per_lang():
    gold = [
        {"a_lang": "en", "a_h": "1", "b_lang": "fi", "b_h": "x", "label": "same"},
        {"a_lang": "en", "a_h": "2", "b_lang": "fi", "b_h": "y", "label": "partial"},
        {"a_lang": "en", "a_h": "3", "b_lang": "de", "b_h": "z", "label": "different"},
        {"a_lang": "en", "a_h": "4", "b_lang": "de", "b_h": "w", "label": "same"},  # not judged: ignored
    ]
    pred = {("en", "1", "fi", "x"): "same", ("en", "2", "fi", "y"): "same", ("en", "3", "de", "z"): "different"}
    r = judge_report(gold, pred)
    assert r["pairs"] == 3 and r["accuracy"] == 0.667
    assert r["per_lang"]["fi"]["accuracy"] == 0.5 and r["per_lang"]["de"]["accuracy"] == 1.0
    assert r["confusion"]["partial->same"] == 1
    assert agreement([])["accuracy"] is None


def test_recall_at():
    assert recall_at([1, 3, None, 7]) == {"R@1": 0.25, "R@5": 0.5, "R@10": 0.75}
