# Gemini in Parallax

Model `gemini-3.8-flash` through the Gemini API is the judge for every cross-edition pair, the claim splitter for pasted AI answers in Check and the English gloss under every quoted sentence.

## 1. The problem

Seven Wikipedia language editions (fi, sv, de, en, ru, et, uk) tell the Winter War differently, and each of them changes over time. A reader sees one edition on one day. Nobody can see where the editions differ, or when one of them stopped saying something the others still say. Parallax lines them up claim by claim on any date and only shows evidence: both sentences, their revisions and links. It never edits Wikipedia.

## 2. How Gemini is integrated

- Endpoint: Gemini's OpenAI-compatible API (`https://generativelanguage.googleapis.com/v1beta/openai/`) with the `openai` Python client, temperature 0, JSON-only answers (`response_format=json_object`), `reasoning_effort=low` (the endpoint rejects `minimal` with HTTP 400 for this model).
- Three prompts in `engine/prompts/`: `judge-v1` (one claim, up to five candidates from other editions, labels same / partial / contradicts / different plus the numbers and terms that differ), `split-v1` (an AI answer into atomic claims) and `gloss-v1` (up to 20 sentences into literal English).
- Robustness: a token bucket of 60 requests per minute shared by the team's one key, at most 4 calls in flight, backoff on 429 and 5xx (Retry-After, else 2 s doubling to 60 s, 5 attempts), one retry on unparseable JSON. A pair that still fails stays "candidate, not judged" in the UI.
- Cache: verdicts are stored in MariaDB keyed by both sentence hashes and the prompt version, so a pair is judged once per prompt and the demo replays without the network.
- Volume so far: 9426 pairs judged in 1457 calls, 0 rate-limit answers; 2606 sentences glossed.

## 3. What is technically interesting

MariaDB's vector search finds the right neighbourhood across languages, but not always the exact twin sentence. Parallax keeps the top five candidates per edition from one SQL statement that combines `FOR SYSTEM_TIME AS OF` and `VEC_DISTANCE_COSINE` (at topic size exact search is faster than the index: 4.0 ms vs 85.18 ms p50), and Gemini decides between them across seven languages and pulls out the numbers and terms that differ ("lavasti" vs "reported", 26 662 vs 25 904). Every verdict sits next to the two original sentences and their `?oldid=` links, so the reader can check the judge.

## 4. Why Gemini matters here, measured

Without the judge there are candidates but no labels, no glosses and no Check.

Agreement with the human gold set: not measured yet (run `make gold label eval`).

