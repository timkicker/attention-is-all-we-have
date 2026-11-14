

def test_not_renewed_leads_with_what_stopped_it():
    from validio.standing.model import DriftFlag, DriftKind
    from validio.standing.renew import _not_renewed

    up = DriftFlag(DriftKind.PER_GUEST_UP, "466375", "The last 2 weeks ...", 1.26, 26)
    gone = DriftFlag(DriftKind.STOCK_BELOW, "466375", "Out of stock at Valio, the usual line is 98 bags.", 0)
    late = DriftFlag(DriftKind.STOCK_BELOW, "466375", "Valio gives no delivery date for it, the usual line is 98 bags.", 0)
    assert _not_renewed(gone, [up]) == "Not renewed: none in stock at Valio. Also 26 % more per guest than usual."
    assert _not_renewed(late, [up]) == "Not renewed: no delivery date from Valio. Also 26 % more per guest than usual."
