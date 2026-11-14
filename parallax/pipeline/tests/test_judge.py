import pytest

from contract.db import connect
from pipeline.judge import tasks


def test_tasks_group_candidates():
    try:
        cur = connect().cursor()
        cur.execute("SELECT COUNT(*) FROM align")
        if not cur.fetchone()[0]:
            pytest.skip("align is empty in this database")
    except Exception:
        pytest.skip("no database")
    for scope, most in (("fi", 3), ("all", 6)):
        t = tasks(cur, "winterwar", scope, "judge-test-never-used")
        assert t and all(1 <= len(x["candidates"]) <= most for x in t)
        assert all(len({c.h for c in x["candidates"]}) == len(x["candidates"]) for x in t)
