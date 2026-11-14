from pipeline.gloss_fill import differs, estimate


def test_differs_follows_the_differences_rule():
    assert differs({"status": "matched", "verdict": {"label": "contradicts"}, "marks": []})
    assert differs({"status": "matched", "verdict": {"label": "partial"}, "marks": [{"this": "25", "other": "30"}]})
    assert not differs({"status": "matched", "verdict": {"label": "partial"}, "marks": [{"this": "25", "other": None}]})
    assert not differs({"status": "matched", "verdict": {"label": "same"}, "marks": []})
    assert not differs({"status": "candidate", "verdict": None, "marks": []})


def test_estimate_counts_batches_per_edition():
    calls, usd = estimate({"fi": {f"h{i}": "x" * 100 for i in range(21)}, "sv": {"a": "y" * 50}})
    assert calls == 3
    assert 0 < usd < 0.01
