from api.marks import extract_numbers, marks_for, number_value


def test_group_separators_and_decimals():
    assert number_value("26 662") == (26662.0, False)
    assert number_value("26 662") == (26662.0, False)
    assert number_value("26.662") == (26662.0, False)
    assert number_value("25,904") == (25904.0, False)
    assert number_value("1.5") == (1.5, False)
    assert number_value("9 %") == (9.0, True)
    assert number_value("13 per cent") == (13.0, True)


def test_extract_keeps_original_spelling():
    got = [n.raw for n in extract_numbers("Soome kaotas 26 662 meest, haavatutena 39 886 meest ja 13 % alast.")]
    assert got == ["26 662", "39 886", "13 %"]


def test_same_number_in_other_spelling_is_no_mark():
    assert marks_for("olivat 26 662 kuollutta", "zählt heute 26.662 gefallene Soldaten", None) == []


def test_differing_number_is_a_mark():
    m = marks_for("tappiot olivat 26 662 kuollutta vuonna 1940", "25,904 people died in 1940", None)
    assert m == [{"kind": "number", "this": "26 662", "other": "25,904"}]


def test_years_pair_only_with_years():
    assert marks_for("sota alkoi 1939 ja 26 662 kuoli", "the war began in 1940", None) == [
        {"kind": "number", "this": "1939", "other": "1940"}
    ]


def test_verdict_numbers_and_terms():
    verdict = {"numbers": [["26 662", "25,904"], ["1939", "1939"]], "terms": [["lavasti", "reported"]]}
    m = marks_for("x", "y", verdict)
    assert {"kind": "number", "this": "26 662", "other": "25,904"} in m
    assert {"kind": "term", "this": "lavasti", "other": "reported"} in m
    assert len(m) == 2


def test_percent_words_count_as_percent():
    m = marks_for("alueet olivat 12 % Suomen pinta-alasta", "included 13 per cent of the assets", None)
    assert m == [{"kind": "number", "this": "12 %", "other": "13 per cent"}]
