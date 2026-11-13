"""The Gemma reader on Modal.

Copied from Modal's own vLLM example (modal.com/docs/examples/vllm_inference): the same image, model,
revision, H200, volumes and serve flags. What we changed: vLLM listens only inside the container on
port 8001, and port 8000 serves reader_api.py, which answers POST /read with a bearer token from the
Modal secret `validio-reader` (READER_TOKEN). The container scales to zero 5 minutes after the last
request and there is never more than one.

Deploy:  modal deploy src/cloud/gemma_app.py          (from validio/)
Stop:    modal app stop validio-gemma
"""

import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import modal

vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.21.0", "transformers==5.8.1")
    .env(
        {
            "HF_XET_HIGH_PERFORMANCE": "1",  # faster model transfers
            "VLLM_LOG_STATS_INTERVAL": "1",  # more frequent metrics logging
        }
    )
    .add_local_file(Path(__file__).parent / "reader_api.py", "/root/reader_api.py")
)

MODEL_NAME = "google/gemma-4-26B-A4B-it"
MODEL_REVISION = "47b6801b24d15ff9bcd8c96dfaea0be9ed3a0301"  # pinned as in Modal's example

hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

FAST_BOOT = False

SPECULATIVE_MODEL_NAME = "google/gemma-4-26B-A4B-it-assistant"
SPECULATIVE_MODEL_REVISION = "f188f476dc11dd5bb3014dc861529d316bce49d3"

app = modal.App("validio-gemma")

N_GPU = 1
GPU = os.environ.get("VALIDIO_READER_GPU", "H200")  # H100 or A100-80GB also hold the 52 GB of weights
MINUTES = 60  # seconds
PORT = 8000  # reader_api, public
VLLM_PORT = 8001  # vLLM, only inside the container


@app.server(
    image=vllm_image,
    gpu=f"{GPU}:{N_GPU}",
    scaledown_window=5 * MINUTES,
    startup_timeout=15 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=[modal.Secret.from_name("validio-reader")],
    port=PORT,
    routing_region="us-east",
    max_containers=1,
    target_concurrency=16,
    unauthenticated=True,  # /read checks its own bearer token
)
class Server:
    @modal.enter()
    def start(self):
        cmd = [
            "vllm",
            "serve",
            MODEL_NAME,
            "--revision",
            MODEL_REVISION,
            "--served-model-name",
            MODEL_NAME,
            "llm",
            "--host",
            "127.0.0.1",
            "--port",
            str(VLLM_PORT),
            "--uvicorn-log-level=info",
            "--async-scheduling",
        ]
        cmd += ["--enforce-eager" if FAST_BOOT else "--no-enforce-eager"]
        cmd += ["--tensor-parallel-size", str(N_GPU)]
        cmd += [
            "--limit-mm-per-prompt",
            json.dumps({"image": 0, "video": 0, "audio": 0}),
            "--enable-auto-tool-choice",
            "--reasoning-parser",
            "gemma4",
            "--tool-call-parser",
            "gemma4",
        ]
        cmd += [
            "--speculative-config",
            json.dumps(
                {
                    "model": SPECULATIVE_MODEL_NAME,
                    "revision": SPECULATIVE_MODEL_REVISION,
                    "num_speculative_tokens": 4,
                }
            ),
        ]
        print(*cmd)
        self.process = subprocess.Popen(cmd)

        base = f"http://127.0.0.1:{VLLM_PORT}"
        deadline = time.time() + 14 * MINUTES
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"vllm exited with {self.process.returncode}")
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=5) as r:
                    if r.status == 200:
                        break
            except OSError:
                pass
            time.sleep(2)
        else:
            raise RuntimeError("vllm did not get healthy in time")

        import uvicorn
        from reader_api import make_app, vllm_chat

        api = make_app(os.environ["READER_TOKEN"], vllm_chat(base, "llm"))
        self.api = threading.Thread(
            target=uvicorn.run, kwargs={"app": api, "host": "0.0.0.0", "port": PORT}, daemon=True
        )
        self.api.start()

    @modal.exit()
    def stop(self):
        self.process.terminate()
