"""Sentences a person reads: whole sentences, each fact once, money as 1,010.00 €, units in words."""

from validio.matching.reasons import option_sentence

WHY = ["Cheapest safe option", "Valio delivered it as ordered every time in its records",
       "Has the Hyvää Suomesta label, which your Spend Pass does not ask for",
       "Footprint 1.1 kg CO2e per kg, a group average"]


def test_accepted_option_is_sentences_not_semicolon_fragments():
    s = option_sentence(WHY, [], [], True)
    assert s == ("Cheapest safe option and Valio delivered it as ordered every time in its records. "
                 "Has the Hyvää Suomesta label, which your Spend Pass does not ask for. "
                 "Footprint 1.1 kg CO2e per kg, a group average.")
    assert ";" not in s


def test_footprint_left_out_when_the_line_note_gives_it():
    s = option_sentence(WHY, [], [], True, carbon=WHY[-1])
    assert "Footprint" not in s and s.endswith("does not ask for.")


def test_price_inside_the_band_keeps_its_own_sentence():
    why = ["30.00 € more than the cheapest, within 5 %, so it counts as equal on price",
           "Valio delivered it as ordered 90 of 100 times"]
    assert option_sentence(why, [], [], True) == (
        "30.00 € more than the cheapest, within 5 %, so it counts as equal on price. "
        "Valio delivered it as ordered 90 of 100 times.")


def test_rejected_option_says_each_reason_once():
    s = option_sentence(["x"], ["Order cut-off 12 Nov 15:00 has passed"], ["the quantity is unknown"], False)
    assert s == "Order cut-off 12 Nov 15:00 has passed. The quantity is unknown."
    assert option_sentence([], ["Sour milk, not plain milk", "Low lactose is not lactose free"], [], False) == \
        "Sour milk, not plain milk. Low lactose is not lactose free."
