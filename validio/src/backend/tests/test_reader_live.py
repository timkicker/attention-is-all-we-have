"""Step 18 live acceptance: the Gemma reader on Modal flags the planted line, 3 runs out of 3,
and the reading never changes a decision. Runs with `make test-live` when MODAL_GEMMA_URL is set."""

import json
import os
from pathlib import Path

import pytest

from validio.config import DEFAULT_ENV, _read_env_file
from validio.reader import read
from validio.reader.remote import ModalReader

pytestmark = pytest.mark.live

PLANTED = json.loads((Path(__file__).parents[1] / "validio/demo/planted.json").read_text())[0]["text"]


@pytest.fixture(scope="module")
def gemma():
    env = {**_read_env_file(DEFAULT_ENV), **os.environ}
    if not env.get("MODAL_GEMMA_URL") or not env.get("MODAL_GEMMA_TOKEN"):
        pytest.skip("MODAL_GEMMA_URL or MODAL_GEMMA_TOKEN not set")
    return ModalReader(env["MODAL_GEMMA_URL"], env["MODAL_GEMMA_TOKEN"], timeout_s=900)


@pytest.mark.parametrize("run", [1, 2, 3])
def test_modal_reader_planted_line(gemma, run):
    got = read(PLANTED, reader=gemma)
    print(run, got.result.model_dump_json())
    assert got.reader == "modal" and not got.fell_back, got.note
    codes = {f.code for f in got.result.flags}
    assert "addresses_agents" in codes


def test_modal_reader_cannot_change_decision(gemma, catalog, tmp_path, monkeypatch):
    """Gemma's real reading of the planted line, forced into every reader, moves nothing."""
    from tests.reader_world import demo_mandate, force_reading, world
    from validio.config import load_settings
    from validio.valio.client import ValioClient

    s = load_settings()
    valio = ValioClient(s.valio_base_url, "", "replay", s.valio_cache)
    mandate = demo_mandate()
    reading = read(PLANTED, reader=gemma)
    assert reading.reader == "modal", reading.note
    before = world(catalog, valio, mandate, tmp_path / "a")
    force_reading(monkeypatch, reading.result)
    assert world(catalog, valio, mandate, tmp_path / "b") == before
