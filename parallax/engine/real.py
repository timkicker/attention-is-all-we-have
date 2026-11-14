"""GeminiEngine: the real engine that contract.engine.get_engine() loads for ENGINE=real (PLAN A9).

embed: bge-m3 through engine.embed (process-wide read-only vector store first).
judge, split_claims, gloss: gemini-3.8-flash.
"""

import os
from pathlib import Path

from contract.engine import LABELS, Candidate, Verdict
from engine import gemini
from engine.embed import embed_texts, shared_store

PROMPTS = Path(__file__).resolve().parent / "prompts"
LANG_NAMES = {
    "fi": "Finnish",
    "sv": "Swedish",
    "de": "German",
    "en": "English",
    "ru": "Russian",
    "et": "Estonian",
    "uk": "Ukrainian",
}


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")


def _pairs(x) -> list[tuple[str, str]]:
    out = []
    for p in x or []:
        if isinstance(p, (list, tuple)) and len(p) == 2:
            out.append((str(p[0]), str(p[1])))
    return out


def parse_judge(data, candidates: list[Candidate]) -> list[Verdict]:
    """Verdicts in candidate order from the judge JSON; a missing or bad entry raises ValueError."""
    results = data.get("results") if isinstance(data, dict) else data
    if not isinstance(results, list):
        raise ValueError("no results list")
    by_i = {}
    for r in results:
        if isinstance(r, dict) and r.get("label") in LABELS:
            try:
                by_i[int(r.get("i"))] = r
            except (TypeError, ValueError):
                continue
    out = []
    for i, c in enumerate(candidates, 1):
        r = by_i.get(i)
        if r is None:
            raise ValueError(f"no verdict for candidate {i}")
        out.append(Verdict(h=c.h, label=r["label"], numbers=_pairs(r.get("numbers")), terms=_pairs(r.get("terms"))))
    return out


class GeminiEngine:
    name = "real"
    model_id = gemini.MODEL

    def __init__(self) -> None:
        self.prompt_version = os.environ.get("JUDGE_PROMPT", "judge-v1")

    def embed(self, texts: list[str]) -> list[list[float]]:
        # One store per process, loaded once; the API never writes shards (only the batch pipeline does).
        return [v.tolist() for v in embed_texts(texts, shared_store())]

    def judge(self, claim: str, claim_lang: str, candidates: list[Candidate]) -> list[Verdict]:
        if not candidates:
            return []
        lines = [f"Claim ({LANG_NAMES.get(claim_lang, claim_lang)}): {claim}", "", "Candidates:"]
        for i, c in enumerate(candidates, 1):
            lines.append(f"{i}. ({LANG_NAMES.get(c.lang, c.lang)}) {c.text}")
        user = "\n".join(lines)
        data, _ = gemini.ask_json(prompt(self.prompt_version), user)
        try:
            return parse_judge(data, candidates)
        except ValueError:
            data, _ = gemini.ask_json(prompt(self.prompt_version), user)
            return parse_judge(data, candidates)

    def split_claims(self, text: str, lang: str | None = None) -> list[str]:
        data, _ = gemini.ask_json(prompt("split-v1"), text)
        claims = data.get("claims") if isinstance(data, dict) else data
        return [str(c).strip() for c in claims or [] if str(c).strip()]

    def gloss(self, texts: list[str], lang: str) -> list[str]:
        out: list[str] = []
        for i in range(0, len(texts), 20):
            chunk = texts[i : i + 20]
            user = f"Language: {LANG_NAMES.get(lang, lang)}\n" + "\n".join(f"{k}. {t}" for k, t in enumerate(chunk, 1))
            data, _ = gemini.ask_json(prompt("gloss-v1"), user)
            g = data.get("gloss") if isinstance(data, dict) else data
            if not isinstance(g, list) or len(g) != len(chunk):
                raise gemini.GeminiError("gloss answer has the wrong length")
            out.extend(str(x) for x in g)
        return out
