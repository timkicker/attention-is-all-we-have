from datetime import datetime, timedelta

from pipeline.lives import walk

T0 = datetime(2010, 1, 1)


def rev(i, minutes, sents, sha1=None, comment=None, ref=()):
    return {
        "rev_id": i,
        "ts": (T0 + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha1": sha1 or f"s{i}",
        "comment": comment or f"c{i}",
        "sentences": [{"h": h, "text": f"text {h}", "section": "[lead]", "has_ref": h in ref} for h in sents],
    }


DAY = 24 * 60


def lives_of(out, h):
    return [lv for lv in out.lives if lv["h"] == h]


def test_born_died_reborn_alive_gives_two_lives():
    revs = [
        rev(1, 0, ["a", "b"]),
        rev(2, 3 * DAY, ["b"], comment="removed a"),
        rev(3, 6 * DAY, ["a", "b"]),
        rev(4, 9 * DAY, ["a", "b", "c"]),
    ]
    out = walk(revs, exact=True)
    a = lives_of(out, "a")
    assert len(a) == 2
    assert a[0]["born_rev"] == 1 and a[0]["died_rev"] == 2 and a[0]["died_comment"] == "removed a"
    assert a[1]["born_rev"] == 3 and a[1]["died_rev"] is None
    assert len(lives_of(out, "b")) == 1 and lives_of(out, "b")[0]["died_rev"] is None
    assert out.counts["lives_raw"] == 4 and out.counts["lives_noise"] == 0 and out.counts["gaps_healed"] == 0


def test_vandal_addition_reverted_after_ten_minutes_gives_no_life():
    revs = [
        rev(1, 0, ["a"], sha1="x"),
        rev(2, DAY, ["a", "junk"], sha1="y"),
        rev(3, DAY + 10, ["a"], sha1="x", comment="Reverted edits"),
        rev(4, 5 * DAY, ["a"], sha1="z"),
    ]
    out = walk(revs, exact=True)
    assert lives_of(out, "junk") == []
    assert out.counts["lives_noise"] == 1


def test_blanking_reverted_after_five_minutes_gives_one_unbroken_life():
    revs = [
        rev(1, 0, ["a", "b"], sha1="x"),
        rev(2, 2 * DAY, [], sha1="blank"),
        rev(3, 2 * DAY + 5, ["a", "b"], sha1="x"),
        rev(4, 4 * DAY, ["a"], sha1="z", comment="trim"),
    ]
    out = walk(revs, exact=True)
    a = lives_of(out, "a")
    assert len(a) == 1 and a[0]["born_rev"] == 1 and a[0]["died_rev"] is None
    b = lives_of(out, "b")
    assert len(b) == 1 and b[0]["died_rev"] == 4 and b[0]["died_comment"] == "trim"
    assert out.counts["gaps_healed"] == 2


def test_gap_closed_by_revert_after_a_week_is_healed():
    revs = [
        rev(1, 0, ["a"], sha1="x"),
        rev(2, 2 * DAY, [], sha1="blank"),
        rev(3, 9 * DAY, ["a"], sha1="x", comment="rv"),
    ]
    assert len(lives_of(walk(revs, exact=True), "a")) == 1


def test_removed_and_readded_three_days_later_gives_two_lives():
    revs = [
        rev(1, 0, ["a"]),
        rev(2, 2 * DAY, []),
        rev(3, 5 * DAY, ["a"]),
    ]
    assert len(lives_of(walk(revs, exact=True), "a")) == 2


def test_snapshot_precision_keeps_short_lives_and_no_comment():
    revs = [rev(1, 0, ["a"]), rev(2, 60, []), rev(3, 120, ["a"])]
    out = walk(revs, exact=False)
    a = lives_of(out, "a")
    assert len(a) == 2 and a[0]["died_comment"] is None
    assert all(lv["time_precision"] == "snapshot" for lv in out.lives)


def test_refs_and_same_second_revisions():
    revs = [
        rev(1, 0, ["a"], ref=("a",)),
        rev(2, 0, ["a"]),  # same second as rev 1
        rev(3, 3 * DAY, ["a"]),
    ]
    out = walk(revs, exact=True)
    (a,) = lives_of(out, "a")
    assert a["had_ref"] == 1 and a["has_ref"] == 0
    starts = [r["ts"] for r in out.revs]
    assert starts == sorted(starts) and len(set(starts)) == 3


def test_section_versions():
    revs = [rev(1, 0, ["a"]), rev(2, DAY * 2, ["a", "b"]), rev(3, DAY * 4, ["a", "b"])]
    out = walk(revs, exact=True)
    lead = [s for s in out.sections if s["section"] == "[lead]"]
    assert len(lead) == 2 and lead[0]["n_sent"] == 1 and lead[1]["n_sent"] == 2 and lead[1]["row_end"] is None


def test_extra_samples_make_the_replacement_continuous():
    # yearly snapshots 1 and 4; the claim c was rewritten to d in edit 3 (rev 2 is the one before it)
    revs = [
        rev(1, 0, ["a", "c"]),
        {**rev(2, 200 * DAY, ["a", "c"]), "adjacent": False},
        {**rev(3, 200 * DAY + 5, ["a", "d"], comment="rewrote c"), "adjacent": True},
        {**rev(4, 365 * DAY, ["a", "d"]), "adjacent": False},
    ]
    out = walk(revs, exact=False)
    (c,) = lives_of(out, "c")
    (d,) = lives_of(out, "d")
    assert c["died_rev"] == 3 and c["time_precision"] == "exact" and c["died_comment"] == "rewrote c"
    assert d["born_rev"] == 3 and d["row_start"] == c["row_end"]  # no gap between claim and replacement
    assert d["died_rev"] is None and d["time_precision"] == "exact"
    (a,) = lives_of(out, "a")
    assert a["time_precision"] == "snapshot" and a["died_comment"] is None


def test_snapshot_walk_without_adjacency_stays_snapshot():
    revs = [rev(1, 0, ["a", "c"]), rev(2, 365 * DAY, ["a"])]
    out = walk(revs, exact=False)
    (c,) = lives_of(out, "c")
    assert c["time_precision"] == "snapshot" and c["died_comment"] is None
