import pytest

from validio.config import load_settings


@pytest.fixture(scope="session")
def catalog():
    from validio.catalog.store import Catalog

    db = load_settings().catalog_db
    if not db.is_file():
        pytest.skip(f"needs_data: {db} missing, run make data index")
    return Catalog(db)
