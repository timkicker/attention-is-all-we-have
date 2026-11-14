from datetime import date

import pytest

from contract.db import connect
from pipeline.align import SQL, anchor_instants


def test_anchor_instants():
    out = anchor_instants(date(2026, 11, 14))
    assert [d for d, _ in out][:5] == ["2006-01-01", "2010-01-01", "2014-01-01", "2018-01-01", "2022-01-01"]
    assert out[-1][0] == "2026-11-14"
    assert all(len(i) == 19 for _, i in out)


def test_sql_has_seven_parameters():
    assert SQL.count("%s") == 7 and "FOR SYSTEM_TIME AS OF" in SQL


def test_align_rows_unique_and_ranked():
    try:
        conn = connect()
    except Exception:
        pytest.skip("no database")
    with conn.cursor() as c:
        c.execute("SELECT COUNT(*) FROM align")
        if not c.fetchone()[0]:
            pytest.skip("align is empty in this database")
        c.execute(
            "SELECT COUNT(*) FROM (SELECT as_of, src_lang, src_page, src_h, dst_lang, dst_h, COUNT(*) n FROM align "
            "GROUP BY 1,2,3,4,5,6 HAVING n > 1) x"
        )
        assert c.fetchone()[0] == 0
        c.execute(
            "SELECT COUNT(*) FROM (SELECT as_of, src_lang, src_page, src_h, dst_lang,"
            " MIN(`rank`) lo, MAX(`rank`) hi, COUNT(*) n "
            "FROM align GROUP BY 1,2,3,4,5 HAVING lo <> 1 OR hi <> n) x"
        )
        assert c.fetchone()[0] == 0
