"""Client for the Gemma reader on Modal: POST {url}/read with a bearer token, strict schema."""

import httpx

from validio.reader.schema import ReaderResult


class ModalReader:
    name = "modal"

    def __init__(self, url: str, token: str, timeout_s: float = 60.0):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout_s = timeout_s

    def read(self, text: str) -> ReaderResult:
        if not self.url or not self.token:
            raise ValueError("MODAL_GEMMA_URL or MODAL_GEMMA_TOKEN is not set")
        r = httpx.post(f"{self.url}/read", json={"text": text},
                       headers={"Authorization": f"Bearer {self.token}"}, timeout=self.timeout_s)
        r.raise_for_status()
        return ReaderResult.model_validate(r.json())
