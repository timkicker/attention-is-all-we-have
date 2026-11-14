# Parallax at scale

Every number on this page comes from the `stat` table, written by the pipeline and by `make bench`. Nothing is typed by hand.

## Dataset M: every revision of 19,742 Finnish articles

| What | Number |
|---|---|
| Articles | 19 742 |
| Revisions parsed (sha1 cache hits) | 862 076 (51 845) |
| Sentence lives before the noise rule | 1 547 051 |
| Vandal lives dropped / blanking gaps healed | 197 013 / 231 575 |
| Sentence lives in `claim_life_fi` | 1 118 463 (alive 586 091) |
| Dead after at least a year | 292 209 |
| Death reasons from edit comments | {'none': 109921, 'other': 402395, 'error': 11609, 'unsourced': 7834, 'speculation': 613} |
| Parse wall time on 7 laptop cores | 8.3 min |
| Load into MariaDB | 33.7 s |
| Contested sentences (3+ lives) | 369 in 168 articles, one SQL statement in 303.5 ms |
| Long lives with a bge-m3 vector | 48 376 lives, 47 057 sentences (100 articles) |

## Time travel latency (`FOR SYSTEM_TIME AS OF`)

| Table | Rows (all versions) | p50 | p95 | Index used |
|---|---|---|---|---|
| Winter War, 7 editions (`claim`) | 59 008 | 2.74 ms | 7.49 ms | `lang` |
| All of M (`claim_life_fi`) | 1 118 463 | 0.86 ms | 1.71 ms | `PRIMARY` |

## Vector search over 26 720 sentence vectors

Vector search in a subquery, the join to `page` after it.

| Method | recall@10 vs exact | p50 | p95 |
|---|---|---|---|
| Exact (`IGNORE INDEX`) | 1.0 | 251.7 ms | 263.03 ms |
| ANN, M=16, ef_search=20 | 0.988 | 7.26 ms | 27.09 ms |
| ANN, M=16, ef_search=80 | 0.993 | 4.98 ms | 8.46 ms |
| ANN, M=16, ef_search=1000 | 0.997 | 18.96 ms | 33.8 ms |

## The demo's statement: time travel and vector search together

`SELECT h, text, VEC_DISTANCE_COSINE(emb, ?) d FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP ? IGNORE INDEX(emb) WHERE topic_id='winterwar' AND lang=? ORDER BY d LIMIT 5`

p50 5.03 ms, p95 13.37 ms over 50 random dates, editions and vectors. At topic size exact search beats the index (alignment probe: exact p50 4.0 ms vs ANN p50 85.18 ms, recall@5 1.0).

## Winter War in seven editions

| Edition | Sentence lives | Alive now | Raw lives | Noise |
|---|---|---|---|---|
| fi | 2 457 | 549 | 7 249 | 1 119 |
| sv | 386 | 154 | 386 | 0 |
| de | 1 036 | 481 | 1 036 | 0 |
| en | 2 688 | 623 | 2 688 | 0 |
| ru | 2 696 | 758 | 2 696 | 0 |
| et | 527 | 188 | 527 | 0 |
| uk | 842 | 467 | 842 | 0 |

Loaded in 23.6 s. 10 486 distinct sentences embedded with bge-m3 at 19.98 sentences/s on the laptop (Ollama).

## Dataset S: atlas of the same topics in fi, sv and en

29 460 shipped article vectors loaded in 58.1 s; coverage {'fi': 11619, 'fi+sv': 2002, 'fi+en': 2335, 'all': 2919}; the three pairwise distances for every topic computed in one SQL statement in 373.9 ms.

## Dataset L: all 568,416 Finnish articles

568 416 articles split into 10 574 397 sentences (10 204 233 distinct) at 55959.3 sentences/s.
Embedding all of L needs a GPU; not run on the laptop.

## Sources

Current revision, ISBN registration groups:

- fi: 184 refs, 82 ISBNs {'FI': 78, 'EN': 4}
- sv: 20 refs, 12 ISBNs {'SE': 7, 'FI': 3, 'EN': 2}
- de: 101 refs, 11 ISBNs {'FI': 4, 'RU/USSR': 2, 'DE': 2, 'EN': 2, 'NL': 1}
- en: 347 refs, 69 ISBNs {'EN': 44, 'FI': 15, 'RU/USSR': 5, 'NL': 2, 'SE': 2, 'NO': 1}
- ru: 50 refs, 94 ISBNs {'RU/USSR': 51, 'FI': 20, 'EN': 16, 'BY': 4, 'DE': 2, 'other': 1}
- et: 56 refs, 8 ISBNs {'EE': 4, 'FI': 3, 'EN': 1}
- uk: 77 refs, 22 ISBNs {'EN': 9, 'FI': 7, 'UA': 2, 'NO': 1, 'SE': 1, 'NL': 1, 'RU/USSR': 1}

## Gemini judge

Calls: {'demo': {'pairs': 9426, 'calls': 1457, 'r429': 0, 'failed': 10, 'minutes': 24.3, 'model': 'gemini-3.8-flash', 'prompt_version': 'judge-v1'}}

Agreement with the human gold set: {}
Alignment recall on gold `same` pairs: None

## Why sentences are the chunks

One vector per article finds the topic, not the fact. Parallax splits every revision into sentences and stores one row per sentence life: the period in which Wikipedia stated it. A sentence that survives 300 edits is one row and one vector, so the vector count grows with distinct sentences, not with revisions. The same row answers "what did the article say on this date" (`AS OF`) and "which sentence in another edition says the same" (`VEC_DISTANCE_COSINE`).

## Sizes

| Table | Current rows | All versions | MB |
|---|---|---|---|
| `claim` | 26 720 | 59 008 | 541.4 |
| `claim_life_fi` | 586 091 | 1 118 463 | 501.5 |
| `article_vec` | 29 460 | 29 460 | 247.8 |
| `section_text` | 210 | 3 914 | 14.9 |
| `revision` | 15 639 | 15 639 | 3.0 |
| `align` | 430 640 | 430 640 | 118.6 |
| `verdict` | 9 441 | 9 441 | 3.5 |
| `ref_stat` | 7 | 161 | 0.1 |
