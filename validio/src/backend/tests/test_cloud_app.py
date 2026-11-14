"""The Modal app file must import inside the container, where Modal places it at /root/app_validio.py and
none of the laptop paths exist. An IndexError there crash-looped the first deploy. No network, no deploy."""

from pathlib import Path

import pytest

modal = pytest.importorskip("modal")  # in the `cloud` extra: uv run --extra cloud pytest

APP_FILE = Path(__file__).resolve().parents[2] / "cloud" / "app_validio.py"


def load_as(path: str, local: bool, monkeypatch) -> dict:
    monkeypatch.setattr(modal, "is_local", lambda: local)
    ns = {"__name__": "app_validio", "__file__": path}
    # our own app file, run under the path Modal gives it in the container
    exec(compile(APP_FILE.read_text(), path, "exec"), ns)  # noqa: S102
    return ns


def test_imports_inside_the_container(monkeypatch):
    ns = load_as("/root/app_validio.py", local=False, monkeypatch=monkeypatch)
    assert ns["app"].name == "validio-web"
    assert isinstance(ns["web"], modal.Function) and isinstance(ns["seed"], modal.Function)
    assert isinstance(ns["fill"], modal.Function)


def test_imports_on_the_laptop(monkeypatch):
    ns = load_as(str(APP_FILE), local=True, monkeypatch=monkeypatch)
    assert ns["ROOT"] == APP_FILE.parents[2]
    assert "fastapi==0.162.7" in ns["_deps"]()


def test_web_function_scales_to_zero_and_stays_single():
    src = APP_FILE.read_text()
    assert "min_containers=0" in src and "max_containers=1" in src
