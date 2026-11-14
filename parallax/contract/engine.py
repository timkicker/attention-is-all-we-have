# parallax/contract/engine.py  (contract, change only on main)
"""The engine interface every track codes against, the deterministic fake engine and get_engine().

ENGINE=fake needs no network: it answers from contract/fixtures/engine/*.json and falls back to
deterministic rules. ENGINE=real loads engine.real.RealEngine, which Track A builds.
"""

import base64
import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Literal, Protocol

import numpy as np

Label = Literal["same", "partial", "contradicts", "different"]
LABELS: tuple[str, ...] = ("same", "partial", "contradicts", "different")
DIM = 1024
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "engine"


@dataclass(frozen=True)
class Candidate:
    lang: str
    page_id: int
    h: str
    text: str


@dataclass(frozen=True)
class Verdict:
    h: str  # the candidate's h
    label: Label
    numbers: list[tuple[str, str]] = field(default_factory=list)  # (in claim, in candidate)
    terms: list[tuple[str, str]] = field(default_factory=list)
    note: str = ""


class Engine(Protocol):
    name: str  # "fake" or "real"
    model_id: str  # judge model id, shown in the UI
    prompt_version: str  # e.g. "judge-v1"

    def embed(self, texts: list[str]) -> list[list[float]]: ...  # 1024 floats each, L2-normalised

    def split_claims(self, text: str, lang: str | None = None) -> list[str]: ...

    def judge(self, claim: str, claim_lang: str, candidates: list[Candidate]) -> list[Verdict]: ...

    def gloss(self, texts: list[str], lang: str) -> list[str]: ...  # English, same order


def normalise(text: str) -> str:
    """Lowercase, Unicode NFC, whitespace collapsed to single spaces, trimmed."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text).lower()).strip()


def claim_hash(text: str) -> str:
    """sha1 of the normalised text as 16 hex characters: the h of every claim row."""
    return hashlib.sha1(normalise(text).encode("utf-8")).hexdigest()[:16]


# Sentence splitter from the spike (PLAN section 2, A3 step 4), shared so hashes agree.
_SPLIT = re.compile(r"(?<=[.!?])\s+")
_GLUE = re.compile(r"\b(\d{1,2}|\w{1,3}|ym|esim|mm|ca|bzw|z\.B|u\.a|т\.е|e\.Kr|jKr|eKr)\.$")


def split_sentences(text: str) -> list[str]:
    pieces: list[str] = []
    for piece in _SPLIT.split(text.strip()):
        if not piece:
            continue
        starts_new = piece[0].isdigit() or piece[0] in '«"„(' or piece[0].isupper()
        if pieces and (not starts_new or len(pieces[-1]) < 25 or _GLUE.search(pieces[-1])):
            pieces[-1] = f"{pieces[-1]} {piece}"
        else:
            pieces.append(piece)
    return [p for p in pieces if len(p) >= 20]


def vec_to_b64(vec) -> str:
    return base64.b64encode(np.asarray(vec, dtype="<f4").tobytes()).decode("ascii")


def b64_to_vec(s: str) -> list[float]:
    return np.frombuffer(base64.b64decode(s), dtype="<f4").astype(float).tolist()


@cache
def _fixture(name: str) -> dict:
    path = FIXTURES / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


class FakeEngine:
    """Deterministic engine for tests, CI and the offline demo. No network."""

    name = "fake"
    model_id = "fake-judge"
    prompt_version = "judge-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        table = _fixture("embed")
        out = []
        for t in texts:
            h = claim_hash(t)
            if h in table:
                out.append(b64_to_vec(table[h]["emb"]))
                continue
            rng = np.random.default_rng(int(h, 16))
            v = rng.standard_normal(DIM)
            out.append((v / np.linalg.norm(v)).tolist())
        return out

    def split_claims(self, text: str, lang: str | None = None) -> list[str]:
        hit = _fixture("split").get(claim_hash(text))
        return list(hit["claims"]) if hit else split_sentences(text)

    def judge(self, claim: str, claim_lang: str, candidates: list[Candidate]) -> list[Verdict]:
        table = _fixture("judge")
        ch = claim_hash(claim)
        out = []
        for c in candidates:
            hit = table.get(f"{ch}:{c.h}")
            if hit:
                out.append(
                    Verdict(
                        h=c.h,
                        label=hit["label"],
                        numbers=[tuple(x) for x in hit.get("numbers", [])],
                        terms=[tuple(x) for x in hit.get("terms", [])],
                        note=hit.get("note", ""),
                    )
                )
            else:
                out.append(Verdict(h=c.h, label="same" if normalise(claim) == normalise(c.text) else "different"))
        return out

    def gloss(self, texts: list[str], lang: str) -> list[str]:
        table = _fixture("gloss")
        out = []
        for t in texts:
            hit = table.get(f"{lang}:{claim_hash(t)}")
            out.append(hit["text_en"] if hit else f"[no gloss] {t}")
        return out


def get_engine() -> Engine:
    """ENGINE=fake -> FakeEngine(); ENGINE=real -> engine.real.RealEngine()."""
    kind = os.environ.get("ENGINE", "fake")
    if kind == "fake":
        return FakeEngine()
    if kind == "real":
        from engine.real import RealEngine  # built by Track A

        return RealEngine()
    raise ValueError(f"ENGINE must be fake or real, not {kind!r}")
