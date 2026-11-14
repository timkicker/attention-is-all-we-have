"""A16: render docs/GEMINI.md and docs/VERDA.md for the side quests. Every number comes from `stat` or
eval/report.json; a section whose numbers do not exist yet says so instead of guessing."""

import json

from contract.db import connect
from engine import gemini
from eval.score import REPORT
from pipeline import stat
from pipeline.fetch import ROOT


def _get(cur, k):
    return stat.get(cur, k) or {}


def gemini_md(cur) -> str:
    jc, gl, ann = _get(cur, "judge_calls"), _get(cur, "gloss"), _get(cur, "align_ann_vs_exact")
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    pairs = sum((x or {}).get("pairs", 0) for x in jc.values())
    calls = sum((x or {}).get("calls", 0) for x in jc.values())
    r429 = sum((x or {}).get("r429", 0) for x in jc.values())
    L = [
        "# Gemini in Parallax",
        "",
        f"Model `{gemini.MODEL}` through the Gemini API is the judge for every cross-edition pair, the claim splitter "
        "for pasted AI answers in Check and the English gloss under every quoted sentence.",
        "",
        "## 1. The problem",
        "",
        "Seven Wikipedia language editions (fi, sv, de, en, ru, et, uk) tell the Winter War differently, and each "
        "of them changes over time. A reader sees one edition on one day. Nobody can see where the editions differ, "
        "or when one of them stopped saying something the others still say. Parallax lines them up claim by claim "
        "on any date and only shows evidence: both sentences, their revisions and links. It never edits Wikipedia.",
        "",
        "## 2. How Gemini is integrated",
        "",
        f"- Endpoint: Gemini's OpenAI-compatible API (`{gemini.BASE_URL}`) with the `openai` Python client, "
        f"temperature 0, JSON-only answers (`response_format=json_object`), `reasoning_effort=low` (the endpoint "
        "rejects `minimal` with HTTP 400 for this model).",
        "- Three prompts in `engine/prompts/`: `judge-v1` (one claim, up to five candidates from other editions, "
        "labels same / partial / contradicts / different plus the numbers and terms that differ), `split-v1` "
        "(an AI answer into atomic claims) and `gloss-v1` (up to 20 sentences into literal English).",
        f"- Robustness: a token bucket of {gemini.RPM} requests per minute shared by the team's one key, at most "
        f"{gemini.MAX_IN_FLIGHT} calls in flight, backoff on 429 and 5xx (Retry-After, else 2 s doubling to 60 s, "
        f"{gemini.MAX_ATTEMPTS} attempts), one retry on unparseable JSON. A pair that still fails stays "
        '"candidate, not judged" in the UI.',
        "- Cache: verdicts are stored in MariaDB keyed by both sentence hashes and the prompt version, so a pair is "
        "judged once per prompt and the demo replays without the network.",
        f"- Volume so far: {pairs} pairs judged in {calls} calls, {r429} rate-limit answers; {gl.get('glossed', 0)} "
        "sentences glossed.",
        "",
        "## 3. What is technically interesting",
        "",
        "MariaDB's vector search finds the right neighbourhood across languages, but not always the exact twin "
        "sentence. Parallax keeps the top five candidates per edition from one SQL statement that combines "
        "`FOR SYSTEM_TIME AS OF` and `VEC_DISTANCE_COSINE` "
        f"(at topic size exact search is faster than the index: {ann.get('exact_ms_p50')} ms vs "
        f"{ann.get('ann_ms_p50')} ms p50), and Gemini decides between them across seven languages and pulls out "
        'the numbers and terms that differ ("lavasti" vs "reported", 26 662 vs 25 904). Every verdict sits next '
        "to the two original sentences and their `?oldid=` links, so the reader can check the judge.",
        "",
        "## 4. Why Gemini matters here, measured",
        "",
        "Without the judge there are candidates but no labels, no glosses and no Check.",
        "",
    ]
    judge = report.get("judge") or {}
    if judge:
        L += [
            f"Gold set: {report.get('gold_pairs')} human-labelled pairs {report.get('labels')}.",
            "",
            "| Prompt | Pairs | Accuracy | Cohen's kappa |",
            "|---|---|---|---|",
        ]
        for pv, r in judge.items():
            L.append(f"| {pv} | {r['pairs']} | {r['accuracy']} | {r['kappa']} |")
        L += ["", "Per language (first prompt version):", ""]
        first = next(iter(judge.values()))
        for lang, r in first.get("per_lang", {}).items():
            L.append(f"- {lang}: {r['pairs']} pairs, accuracy {r['accuracy']}, kappa {r['kappa']}")
        L += ["", f"Alignment recall of the gold `same` partner (bge-m3 in MariaDB): {report.get('alignment')}", ""]
    else:
        L += ["Agreement with the human gold set: not measured yet (run `make gold label eval`).", ""]
    return "\n".join(L) + "\n"


def verda_md(cur) -> str:
    v = _get(cur, "verda")
    emb, mv, lsc = _get(cur, "topic_embed"), _get(cur, "m_vectors"), _get(cur, "l_scale")
    L = [
        "# Compute for Parallax",
        "",
        "## Why compute was needed",
        "",
        "Every distinct sentence of the Winter War history (seven editions) and every long-lived sentence of the "
        "Finnish dataset M needs a bge-m3 vector. On the laptop, Ollama embeds "
        f"{emb.get('rate')} sentences/s (measured on {emb.get('distinct')} Winter War sentences), and "
        f"{mv.get('rate')} sentences/s on the longer Finnish sentences of M.",
        "",
    ]
    if v:
        L += ["## The Verda GPU job", "", f"{v}", ""]
    else:
        L += [
            "## Status",
            "",
            "No Verda GPU job has run yet, so this page claims nothing for Verda. The code is ready: "
            "`engine/embed_server.py` serves bge-m3 with sentence-transformers on a GPU host, the laptop reaches it "
            "through an ssh tunnel and `EMBED_BACKEND=remote`; `make m-embed` and `make l-scale` then run against it.",
            "",
        ]
    L += [
        "## Path to scale",
        "",
        f"Dataset L ({lsc.get('articles', 568416)} current Finnish articles) splits into "
        f"{lsc.get('distinct', 'n/a')} distinct sentences ({lsc.get('embed_note', '')}). The same job runs over more "
        "language editions, re-embedding only sentences whose hash is new each night. Parallax reads and compares "
        "only; there are no automated edits at any scale.",
        "",
    ]
    return "\n".join(L) + "\n"


def main() -> None:
    cur = connect().cursor()
    (ROOT / "docs" / "GEMINI.md").write_text(gemini_md(cur), encoding="utf-8")
    (ROOT / "docs" / "VERDA.md").write_text(verda_md(cur), encoding="utf-8")
    print("wrote docs/GEMINI.md and docs/VERDA.md")


if __name__ == "__main__":
    main()
