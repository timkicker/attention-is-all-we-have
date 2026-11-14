"""`make video`: a scripted screen recording of the five demo scenes, for when nobody records by hand.

It builds the web app (VITE_API=live), seeds a store of its own under artifacts/video/store, starts the
API on a free port with replayed Valio answers (no network) and runs src/frontend/scripts/record-video.mjs.
That one opens a 1920x1080 stage in headless Firefox: the agent's terminal on the left third, the web
app on the right. It clicks through the shots of scripts/video_shots.json and pads each shot to its
voice-over length. Output: artifacts/video/validio-demo.webm, plus .mp4 when ffmpeg is installed.
Nothing is uploaded."""

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
FRONTEND = ROOT / "src" / "frontend"
OUT = ROOT / "artifacts" / "video"
TAKEN = {8410, 8416, 8418, 8419, 8420}  # make demo, demo-smoke, demo-check, e2e-live, a11y
DROP = ("VALIO_API_KEY",)  # replay only: the recording never needs Valio's key


def free_port() -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in TAKEN:
            return port


def server_env(store: Path, code: str, base: dict, keep_model_key: bool = False) -> dict:
    env = {k: v for k, v in base.items() if k not in DROP and (keep_model_key or k != "GEMINI_API_KEY")}
    env.update(VALIO_MODE="replay", VALIDIO_DB=str(store / "validio.db"), VALIDIO_KEYS=str(store / "keys"),
               VALIDIO_DEMO="1", VALIDIO_APPROVE_CODE=code, NO_COLOR="1")
    return env


def encode_command(ffmpeg: str, raw: Path, out: Path, lead: float, seconds: float) -> list[str]:
    """Keep the shots only (no lead-in, no closing frames) and encode: H.264 for .mp4, VP8 for .webm."""
    codec = (["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart"]
             if out.suffix == ".mp4" else ["-c:v", "libvpx", "-b:v", "3M", "-deadline", "realtime", "-cpu-used", "8"])
    return [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{lead:.2f}", "-i", str(raw), "-t", f"{seconds:.2f}", "-an", *codec,
            str(out)]


def wait_health(base: str, proc: subprocess.Popen, seconds: float = 60) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if proc.poll() is not None:
            raise SystemExit(f"the server stopped with exit code {proc.returncode}")
        try:
            if httpx.get(f"{base}/api/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    raise SystemExit(f"no answer from {base}/api/health after {seconds:.0f} s")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="record_video", description=__doc__.splitlines()[0])
    ap.add_argument("--no-build", action="store_true", help="use the web app already in src/frontend/build")
    ap.add_argument("--keep-model-key", action="store_true", help="let the agent use Gemini if GEMINI_API_KEY is set")
    a = ap.parse_args(argv)

    store, raw = OUT / "store", OUT / "raw"
    shutil.rmtree(store, ignore_errors=True)
    shutil.rmtree(raw, ignore_errors=True)
    store.mkdir(parents=True)
    port, code = free_port(), f"{secrets.randbelow(10**6):06d}"
    base = f"http://127.0.0.1:{port}"
    env = server_env(store, code, dict(os.environ), a.keep_model_key)

    if not a.no_build:
        subprocess.run(["npm", "run", "build"], cwd=FRONTEND, env={**env, "VITE_API": "live"}, check=True,
                       stdout=subprocess.DEVNULL)
    subprocess.run(["uv", "run", "python", "../../scripts/seed_demo.py"], cwd=BACKEND, env=env, check=True,
                   stdout=subprocess.DEVNULL)
    server = subprocess.Popen(["uv", "run", "uvicorn", "validio.api.app:app", "--host", "127.0.0.1", "--port",
                               str(port), "--log-level", "warning"], cwd=BACKEND, env=env)
    try:
        wait_health(base, server)
        print(f"server on {base}, store {store.relative_to(ROOT)}", flush=True)
        drive = subprocess.run(["node", "scripts/record-video.mjs"], check=False, cwd=FRONTEND, env={
            **env, "VIDEO_BASE": base, "VIDEO_CODE": code, "VIDEO_RAW": str(raw),
            "VIDEO_SHOTS": str(ROOT / "scripts" / "video_shots.json")})
        if drive.returncode != 0:
            return drive.returncode
    finally:
        server.terminate()
        server.wait(timeout=20)

    (got,) = sorted(raw.glob("*.webm"))
    run = json.loads((raw / "run.json").read_text())
    webm = OUT / "validio-demo.webm"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        shutil.copy(got, webm)
        print(f"video: {webm.relative_to(ROOT)} (no ffmpeg on PATH: lead-in of {run['leadSeconds']:.1f} s kept, no mp4)")
        return 0
    for out in (webm, webm.with_suffix(".mp4")):
        subprocess.run(encode_command(ffmpeg, got, out, run["leadSeconds"], run["totalSeconds"]), check=True)
        print(f"video: {out.relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
