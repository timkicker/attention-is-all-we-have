"""`make video` (scripts/record_video.py): the shot plan follows the video script, the server it starts
is offline and on its own port, and the mp4 is a plain ffmpeg conversion of the webm."""

import importlib.util
import itertools
import json
import socket
from pathlib import Path

VALIDIO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("record_video", VALIDIO / "scripts" / "record_video.py")
rv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rv)


def test_shots_follow_the_video_script():
    shots = json.loads((VALIDIO / "scripts" / "video_shots.json").read_text())["shots"]
    assert [s["scene"] for s in shots] == [1, 2, 3, 4, 5]
    assert [s["start"] for s in shots] == [0, 15, 45, 75, 105]
    assert sum(s["seconds"] for s in shots) == 120
    for a, b in itertools.pairwise(shots):
        assert a["start"] + a["seconds"] == b["start"]


def test_free_port_is_free_and_not_the_demo_port():
    port = rv.free_port()
    assert port not in (8410, 8416, 8418, 8419, 8420)
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))


def test_server_env_is_offline_with_its_own_store(tmp_path):
    env = rv.server_env(tmp_path, "123456", {"VALIO_API_KEY": "k", "GEMINI_API_KEY": "g", "PATH": "/bin"})
    assert env["VALIO_MODE"] == "replay"
    assert env["VALIDIO_DB"] == str(tmp_path / "validio.db")
    assert env["VALIDIO_KEYS"] == str(tmp_path / "keys")
    assert env["VALIDIO_APPROVE_CODE"] == "123456"
    assert "VALIDIO_DEMO_TOKEN" not in env
    assert env["NO_COLOR"] == "1"
    assert "VALIO_API_KEY" not in env and "GEMINI_API_KEY" not in env
    assert env["LLM_MODE"] == "fake"  # a key in validio/.env must not switch the recording to Gemini
    assert env["PATH"] == "/bin"


def test_server_env_keeps_the_gemini_key_only_when_asked(tmp_path):
    env = rv.server_env(tmp_path, "1", {"VALIO_API_KEY": "k", "GEMINI_API_KEY": "g"}, keep_model_key=True)
    assert env["GEMINI_API_KEY"] == "g" and "VALIO_API_KEY" not in env
    assert "LLM_MODE" not in env


def test_encode_cuts_the_lead_in_and_converts(tmp_path):
    raw = tmp_path / "raw.webm"
    mp4 = rv.encode_command("ffmpeg", raw, tmp_path / "a.mp4", 3.25, 120.0)
    assert mp4[0] == "ffmpeg" and mp4[mp4.index("-ss") + 1] == "3.25" and mp4[mp4.index("-i") + 1] == str(raw)
    assert mp4[mp4.index("-t") + 1] == "120.00"  # the two minutes the submission allows, not the closing frames
    assert mp4.index("-ss") < mp4.index("-i")  # cut before decoding
    assert "libx264" in mp4 and "yuv420p" in mp4 and mp4[-1] == str(tmp_path / "a.mp4")
    webm = rv.encode_command("ffmpeg", raw, tmp_path / "a.webm", 3.25, 120.0)
    assert "libvpx" in webm and webm[-1] == str(tmp_path / "a.webm")
