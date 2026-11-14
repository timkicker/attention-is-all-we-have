import pytest

from contract.db import connect


@pytest.fixture(scope="session")
def db():
    """The Parallax database with contract/schema.sql and seed-mini (or a bigger seed) loaded."""
    conn = connect()
    yield conn
    conn.close()


@pytest.fixture
def cur(db):
    with db.cursor() as c:
        yield c
