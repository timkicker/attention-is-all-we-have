"""`validio-agent`: the pane as a command, plus --print-pass for a third-party agent."""

import sqlite3
import tomllib
from pathlib import Path

from validio.agent import cli


def test_entry_point_declared():
    toml = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert toml["project"]["scripts"]["validio-agent"] == "validio.agent.cli:main"


def test_print_pass_prints_the_issued_pass(ctx, capsys):
    assert cli.main(["--print-pass"]) == 0
    (issuance,) = sqlite3.connect(ctx.db_path).execute("select issuance from spend_pass").fetchone()
    assert capsys.readouterr().out.strip() == issuance


def test_local_scene4_prints_pane_and_writes_transcript(catalog, tmp_path, capsys, monkeypatch):
    from validio.api.state import set_ctx

    monkeypatch.setattr(cli, "ARTIFACTS", tmp_path)
    monkeypatch.setenv("VALIDIO_DB", str(tmp_path / "unused.db"))  # restored after; --local sets its own
    monkeypatch.setenv("VALIDIO_KEYS", str(tmp_path / "unused-keys"))
    set_ctx(None)
    assert cli.main(["--scene", "4", "--local"]) == 0
    out = capsys.readouterr().out
    assert "agent -> renew_steady_order" in out and "waits for the chef:" in out
    assert (tmp_path / "scene-4.md").is_file()
    set_ctx(None)
