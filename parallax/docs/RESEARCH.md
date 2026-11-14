# Parallax research

Research notes behind [PRODUCT.md](PRODUCT.md) and [PLAN.md](../PLAN.md), written on 14 November 2026. Web sources were retrieved that day. Local sources are named by what they are: the challenge text c-307, the README files of MariaDB's three starter repos and the files of our spike on the night of 13 November (scripts such as `sentences.py`, outputs such as `stat-NN.json`, `candidates.json`, `spike-run1.txt`, `spike-scale.txt` and `gemma-check.txt`). The spike files are not in this repo yet. **(unverified)** marks a fact we could not find in a saved file or on the web. **(inference)** marks our own reasoning.

Starter repos:
- DS: https://github.com/MariaDB/mariadb-wikipedia-datasets
- SVT: https://github.com/MariaDB/mariadb-system-versioning-wikipedia
- RAG: https://github.com/MariaDB/mariadb-vector-wikipedia-rag

## 1. Challenge

### What MariaDB asks for

- Headline: "Build the tools Wikipedia is missing, powered by MariaDB's vector search (RAG) and system-versioned tables."
- Mission: "build a tool for Wikipedia that doesn't exist yet" with "MariaDB at the core of your stack".
- RAG track, "recommended for most teams": use native vector search for "grounded, source-cited answers".
- SVT track, "for advanced teams": "tools that query how knowledge changes over time", for example "showing what an article said on any given date".
- Both, "for very advanced teams", with the example of a RAG assistant that says what Wikipedia said about something in 2015 and what has changed since. Parallax sits here.
- Insight paragraph: language models have "a particular world view" from their training data that "may differ from Wikipedia's world view, which strives for NPOV". It also asks for tools that make Wikipedia "easier to digest, verify and trust, such as source-grounded Q&A, fact-checking assistants" and for "'time-travel' tools that reveal how articles evolve".
- Two user groups are named: Wikipedia readers and active Wikipedians. Teams may pick either or both.

### Judging

| Criterion | Weight | Text |
|:---|:---|:---|
| Effective and Creative use of MariaDB | 20 % | "Effective and creative use of MariaDB RAG and/or system-versioned tables" |
| Implementation | 20 % | "Technical execution and scalability across the provided datasets" |
| Usefulness | 20 % | "Real-world usefulness for Wikipedia readers or editors" |
| Design and demo quality | 20 % | |
| Originality | 20 % | "The most original and unique implementation of the project" |
| Bonus | 0 % | "Added technical ambition for teams taking on the SVT track or combining both tracks" |

The prose says SVT and combined teams "will be recognised for the added technical ambition", but the scored weight is 0 %. "Scalability across the provided datasets" means a demo on one article loses Implementation points **(inference)**.

Prizes: 1st 1,000 € cash, 1,000 € UpCloud credits and MariaDB certification vouchers. 2nd 500 €, 3rd 250 €. Winners are credited in a blog post on mariadb.org.

### Data

The challenge offers "datasets in three sizes (small, medium and large) drawn from Finnish Wikipedia articles on the history of Finland" and recommends a multilingual embedding model. Per the DS README:

- **S**: 19,285 Finnish, 4,921 Swedish and 5,254 English articles, current text (FineWiki, August 2025), one bge-m3 vector of 1024 dimensions per article. 156 MB.
- **M**: 19,742 Finnish articles with every version up to 1 October 2026, 862,076 versions with 12.2 GB of raw wikitext, user, edit summary and sha1. No vectors. 315 MB.
- **L**: 568,416 Finnish articles, current text, no vectors. 495 MB.

M has the columns `page_id, title, rev_id, parent_id, timestamp (UTC), user, anonymous, comment, minor, sha1, bytes, text`. 19 % of the versions are anonymous, which since 2025 includes temporary accounts named like `~2026-33532-4`. Versions hidden by administrators are not in the data. The data is CC BY-SA 4.0 and the S vectors carry the same licence. The scripts are MIT.

### Required tech

MariaDB has to be at the core. Teams may pair it "with any LLM, embedding model or frontend framework". The challenge prescribes no version. The starters use `mariadb:lts`, which was 12.3.3 in October 2026. Vector search needs 11.7 or later (RAG README) and `system_versioning_insert_history` needs 10.11 or later (SVT README). The mentors are Kaj Arnö and Robert Silén of the MariaDB Foundation. Robert Silén wrote all three starters, which their README says were built with Claude Code.

### Side challenges that fit

- **Verda** (challenge text c-56) names our use case: "Embed MariaDB's full Wikipedia dataset with batch jobs and serve a RAG assistant on top." It asks teams to document the process and post a summary link in its Discord channel. Four criteria at 25 % each: ambition, fit, working prototype, path to scale. Credits per team are not stated. Every team gets some (https://verda.com/blog/junction-2026).
- **Nemotron** (challenge text c-46): free NVIDIA API, "about 40 requests per minute per key" as developer forums report. The submission needs a text on the model, what it does, why it matters and how its output was improved.

## 2. Spike claims checked

### Numbers

Summed over the 16 `stat-NN.json` files: 862,076 versions, 19,742 articles, 46,402,122 sentence occurrences, 1,052,406 distinct sentences per article, 572,462 dead, 337,299 dead after 30 days, 223,693 dead after a year, 11,835,245,791 text characters, 2,731.7 seconds of processing. 479,944 are alive.

| Claim | Status | Source |
|:---|:---|:---|
| 862,076 versions | confirmed, matches the DS README | stat files |
| 19,742 articles | confirmed, matches the DS README | stat files |
| 1,052,406 sentences | confirmed as distinct sentences per article (the same sentence in two articles counts twice) | stat files, `sentences.py` |
| 223,693 dead after at least a year | confirmed. The year is the **total** time alive over all lives, not one continuous life. Dead means missing from the article's last version | stat files, `sentences.py` |
| 479,944 alive, 572,462 dead | confirmed | stat files |
| 11.8 GB of wikitext | the field counts characters, not bytes. The README says 12.2 GB. Both fit, because ä and ö take two bytes in UTF-8 | `sentences.py`, DS README |
| 6,399 removed claims with a keyword comment | confirmed, length of `candidates.json` | own count |
| 144,711 reworded, 78,978 gone | **(unverified)**. `candidates.py` printed them and nothing saved them | `candidates.py` |
| 1,948 lived two years or more with an error comment | **(unverified)**. `candidates.json` has 4,925 entries of two years or more with the Finnish keyword filter. The 1,948 came from a narrower filter that was not saved | own count |
| Gemma's dead claim at rank 12 of 148 (0.479), the short restatement first at 0.268 | **(unverified)**. Only the raw run is saved | `gemma-check.txt` |
| Gemma said the 1990s depression "was considerably milder than the Great De[pression]" | confirmed | `gemma-check.txt` |
| "Se ei kuitenkaan ollut niin paha kuin 1930-luvun lama." stood 2.3 years, removed 27 May 2008 as "lähteetön väite" by an anonymous editor | confirmed | `candidates.json`, page 89865 |
| The Sámi claim on "mongolidisesta perimästä" stood 9.8 years, removed 10 October 2020 with "Poistettu kaksi lähteetöntä ja varsin spekulatiivista kappaletta." | confirmed | `candidates.json`, page 7283 |
| Hennala, "yli 500 vankia" with about 200 women, stood 4.3 years, removed 18 May 2018 by an editor who cites the National Archives | confirmed. The same edit also removes another researcher's figures, so it is a contested removal and not a clear correction | `candidates.json`, page 1151714 |

The stat files come from two script versions: files 01 to 15 carry `read_s` from the old loader that read whole files, file 16 comes from the streaming rewrite. That the streaming version gave the same output on file 06 is noted in our idea evaluation but the comparison is not saved **(unverified)**.

The splitter noise is real and not fixed yet. `spike-run1.txt` shows link fragments (`[[Hankoniemi|Hankoniemellä.`) and sentences cut at ordinal dates ("…vuokraus. 12."). Every count above is from before a fix.

### Vector index on a system versioned table

It worked on a small scale.

- Schema in `spike_load.py`: `claim` with `emb VECTOR(1024) NOT NULL`, `PERIOD FOR SYSTEM_TIME(row_start,row_end)`, `VECTOR INDEX(emb) M=16 DISTANCE=cosine` and `WITH SYSTEM VERSIONING`. History rows were written with `SET system_versioning_insert_history=1` and explicit `row_start` and `row_end`.
- `EXPLAIN` uses the `emb` index for current rows and for `FOR SYSTEM_TIME ALL` (`spike-run1.txt`).
- `FOR SYSTEM_TIME AS OF TIMESTAMP '2010-01-01' ORDER BY VEC_DISTANCE_COSINE(...) LIMIT 3` returned rows with periods from 2006 to 2011 in 0.8 ms. The graveyard query `FOR SYSTEM_TIME ALL WHERE row_end < NOW()` took 0.7 ms.
- On 3,999 rows of 66 articles (1,576 current) the index matched exact search in the top 10 at 0.997 now, 1.000 `AS OF` 2012 and 1.000 over all rows. The index took a median of 0.8 to 1.3 ms, exact search 84 to 273 ms (`spike-scale.txt`, `spike_scale.py` with `mhnsw_ef_search=80`).
- Tested with one article (85 rows) and 66 articles (3,999 rows). **Not tested at a million rows.**
- `spike_scale.py` inserts each sentence once from its first birth to its last death, so a sentence that died and came back gets one period that covers the gap. `spike_load.py` keeps the separate lives.
- Current rows show `row_end` as `2106-02-07 06:28:15.999999`. The docs give `2038-01-19 03:14:07.999999` as the maximum (https://mariadb.com/docs/server/reference/sql-structure/temporal-tables/system-versioned-tables), so 12.x evidently uses the wider TIMESTAMP range. Queries should use `row_end < NOW()` or `AS OF` and never a fixed end value **(inference)**.

### MariaDB version

`docker image inspect mariadb:lts` gives 12.3.3 (`MARIADB_VERSION=1:12.3.3+maria~ubu2404`) and the spike container logged `Version: '12.3.3-MariaDB-ubu2404'`. Confirmed: 12.3.3.

### How the dataset was built

The M parquet files come from the `m-2026-10` release with `SHA256SUMS`. Upstream they were built from the 16 history files of the fiwiki dump of 1 October 2026, streamed through 7-Zip and filtered to the article list (DS README). That dump is complete and lists about 3,889 MB in a section marked "Deprecated: All pages with complete edit history (.7z)" (https://dumps.wikimedia.org/fiwiki/20261001/). The README says 4.5 GB. The difference is probably MB against MiB plus other files **(inference)**.

`sentences.py` streams each file in batches of 256 rows, groups by page, strips comments, templates, tables and file links, splits prose lines at `.!?` followed by a capital or a digit and keeps sentences of at least 40 characters with a space. It hashes the normalised text (blake2b, 64 bits) and records birth, total time alive and every death with user, anonymous flag and edit comment. `candidates.py` keeps dead sentences with at least a year alive whose Jaccard similarity to every living sentence of the same article is under 0.35 (tokens of four or more characters) and then filters on Finnish keywords in the death comment.

## 3. New facts from the web

### System versioned tables

Source: https://mariadb.com/docs/server/reference/sql-structure/temporal-tables/system-versioned-tables

- `FOR SYSTEM_TIME AS OF`, `BETWEEN a AND b` (both ends included), `FROM a TO b` (end excluded) and `ALL` (a MariaDB extension). The clause goes right after the table name, before the alias.
- `system_versioning_insert_history` (default off, since 10.11.0) allows direct inserts into the row start and end, "only if secure_timestamp permits changing timestamp".
- `ALTER TABLE` on a versioned table is blocked by default (`system_versioning_alter_history = ERROR`). `KEEP` allows it but the history becomes wrong. The schema has to be final before the big load.
- `TRUNCATE` is refused (error 4137).
- Transaction precise history (`AS OF TRANSACTION`) is InnoDB only and cannot be partitioned by system time. We need Wikipedia's timestamps, so it does not matter to us.
- `mariadb-dump` writes the history only with `--dump-history` (10.11 or later). This matters if we ship a SQL dump.
- `PARTITION BY SYSTEM_TIME` with `INTERVAL` and `AUTO` exists since 10.9. The SVT starter measured no speed up at its size, because "as of 2005" still reads 23 of 25 partitions. The extra `KEY(page_id,row_start)` is what helped.
- Limits the SVT starter met: no `CREATE TEMPORARY TABLE` with system versioning, a prepared statement's `TIMESTAMP ?` refuses a bare date and a batch of long versions exceeds the default 16 MB packet. Two edits in the same second: shift the second one by 1 µs. Always `SET time_zone='+00:00'`.

Application time periods (https://mariadb.com/docs/server/reference/sql-structure/temporal-tables/application-time-periods): `PERIOD FOR p(start_col, end_col)` with DATE, TIMESTAMP or DATETIME columns of the same type, `UPDATE … FOR PORTION OF` and `DELETE … FOR PORTION OF` and `UNIQUE (key, p WITHOUT OVERLAPS)`. The page shows no `SELECT … FOR p AS OF`, so application periods are filtered with a plain `WHERE`. A table can carry both kinds of period (bitemporal). One use would be the system period as the time Wikipedia stated a claim and an application period as the time the claim holds in the world, for example a term of office **(inference)**. Not needed for the core.

### MariaDB Vector

Sources: https://mariadb.com/docs/server/reference/sql-structure/vectors/vector-overview, https://mariadb.com/docs/server/reference/sql-structure/vectors/create-table-with-vectors, https://mariadb.com/docs/server/reference/sql-structure/vectors/vector-system-variables, https://mariadb.org/wp-content/uploads/2025/02/vector-search.html

- `VECTOR(N)` stores 32 bit floats. It came in Community Server 11.7. 11.8 is the first LTS with it and Enterprise backported it to 11.4.5-3.
- `VECTOR INDEX (col) M=… DISTANCE=euclidean|cosine` is a modified HNSW. `M` runs from 3 to 200 with a default of 6. The default distance is euclidean.
- `mhnsw_ef_search` defaults to 20 (range 1 to 10000). `mhnsw_max_cache_size` defaults to 16 MB. With bge-m3 vectors the RAG starter measured 79 % recall at the defaults and 100 % at `M=16` with `ef_search=80`. The spike used those settings.
- Functions: `VEC_DISTANCE_EUCLIDEAN`, `VEC_DISTANCE_COSINE`, `VEC_DISTANCE` (takes the metric from the index), `VEC_FromText` and `VEC_ToText`.
- The index is used only for `ORDER BY VEC_DISTANCE_*(col, const) ASC LIMIT n` with the index's metric. A bare `WHERE distance < x` scans the table.
- Limits: one vector index per table, the indexed column must be `NOT NULL` and the dimension is fixed per index. The 2025 slides add: only InnoDB, MyISAM and Aria, no XA and "Partitioning is not supported". MariaDB's own test `vector_partition.test` checks that a vector index on a partitioned table fails with "Partitioned tables do not support VECTOR" (https://sources.debian.org/src/mariadb/1%3A11.8.3-1/mysql-test/main/vector_partition.result).
- So the `claim` table cannot use the SVT starter's `PARTITION BY SYSTEM_TIME` while it has a vector index. The spike did not partition. Checked for 11.8 only and not again on 12.3.3.
- A flat join with `ORDER BY distance LIMIT` falls back to a full scan (21,723 rows, about 50 ms). The RAG starter puts the vector search in a subquery and joins after it (about 1 ms).
- Vector is part of the Community Server under GPLv2 (https://www.infoq.com/news/2025/06/mariadb-vector-search, from an earlier note, not fetched again).

### Wikimedia dumps and APIs

- Dumps: "Downloads are also rate limited and capped at 3 connections per-IP." (https://dumps.wikimedia.org/). Dataset M already holds the dump content, so we do not need them.
- API limits, new in 2026 (https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits): 10 requests a minute for clients known only by IP, 200 for bots without login that send a proper User-Agent, 2,000 for established editors. Flagged bots and Cloud Services are exempt. Over the limit comes HTTP 429 with `Retry-After`. Without one, wait at least 5 seconds or back off. The RAG starter's "200 requests a minute per IP" holds only with a proper User-Agent.
- Etiquette (https://www.mediawiki.org/wiki/API:Etiquette): requests in series, `maxlag` for background jobs, a meaningful User-Agent or the IP "may be IP-blocked without notice", titles batched with `|`.
- Old version links need no API: `https://fi.wikipedia.org/?oldid=<rev_id>` (DS README). Edits after 1 October 2026 and pageviews would need it. Our idea evaluation measured that the pageviews REST call returns an article's whole history in one request.
- WikiWho supports Finnish as one of 70 editions (https://wikiwho-api.wmcloud.org/).

### Licence

- Dump text is under the GFDL and CC BY-SA 4.0 (https://dumps.wikimedia.org/legal.html).
- Attribution is a link to the page reused, a link to a stable free copy that credits the authors or a list of authors (https://en.wikipedia.org/wiki/Wikipedia:Reusing_Wikipedia_content).
- Changed text stays under CC BY-SA 4.0 or later. Changes must be marked and each copy must name the licence with a link (https://creativecommons.org/licenses/by-sa/4.0/).
- For us **(inference)**: every claim we show links its `?oldid=` version, whose history lists the authors. The footer says "Text from Finnish Wikipedia, CC BY-SA 4.0, modified: split into sentences". A published claim table is CC BY-SA too. The code stays MIT like the starters. Showing the username of the editor who removed a claim is fine as attribution, but a ranking of named editors would target people.

### Related work

| Work | What it does | How it differs | Source |
|:---|:---|:---|:---|
| VitaminC, Schuster, Fisch, Barzilay, NAACL 2021 | more than 100,000 Wikipedia revisions that changed a fact, used for contrastive fact verification training (more than 400,000 claim and evidence pairs) | training data, no tool, no check of model output | https://arxiv.org/abs/2103.08541 |
| TemporalWiki, Jang et al., EMNLP 2022 | diffs of consecutive English Wikipedia snapshots to update models, Wikidata changes for evaluation | benchmark for continual learning | https://arxiv.org/abs/2204.14211 |
| WikiFactDiff, Ammar Khodja et al., LREC-COLING 2024 | Wikidata facts that are new, obsolete or unchanged between January 2021 and February 2023, for knowledge editing | Wikidata triples instead of prose, a dataset instead of a tool | https://arxiv.org/abs/2403.14364 |
| Dated Data, Cheng et al., 2024 | monthly Wikipedia versions from April 2016 to April 2023. The perplexity minimum gives a model's effective cutoff, often not the one reported | closest in spirit, dates a model against Wikipedia's history. Uses perplexity instead of claims and is no reader tool | https://arxiv.org/abs/2403.12958 |
| FreshLLMs and FreshQA, Vu et al., 2023 | questions on fast changing facts and false premises. Web search fixes outdated answers | fixes stale answers with search, not with Wikipedia's history | https://arxiv.org/abs/2310.03214 |
| Retracted papers on Wikipedia, Shi, Yu, Romero, Horvát, 2025 | 1,181 citations of retracted papers, 71.6 % problematic, staying a median 3.68 years (1,344 days) | decay from the source side, analysis only | https://arxiv.org/abs/2509.18403 |
| Pew, "When Online Content Disappears", 2024 | of 50,000 English Wikipedia pages, 11 % of reference links are dead and 53 % of pages have at least one broken reference link (the summary says 54 %) | link rot instead of claim removal | https://www.pewresearch.org/data-labs/2024/05/17/when-online-content-disappears/ |

### What a juror might call prior art

| Prior art | Overlap | Our answer | Source |
|:---|:---|:---|:---|
| CLAIRE (Stanford, EMNLP 2025): a model finds contradictions inside today's English Wikipedia. At least 3.3 % of facts contradict another one and editors found 64.7 % more inconsistencies with it | fact checking on Wikipedia with models | today's consistency, not history. No check of model answers | https://arxiv.org/abs/2509.23233 |
| Hoaxes, Kumar, West, Leskovec, WWW 2016: more than 20,000 hoax articles, 1 % survive more than a year | survival of false content | whole hoax articles in English, detected at creation. We follow sentences in real articles | https://cs.stanford.edu/~srijan/hoax |
| Who Wrote That? (Wikimedia browser extension on WikiWho, Finnish supported) | age and author of a sentence | authorship of living text only, no dead claims, no matching by meaning | https://meta.wikimedia.org/wiki/Community_Tech/Who_Wrote_That_tool/en |
| WikiBlame and Wikipedia's own history and diff pages | view as of a date | the challenge's own example, we build on it | well known |
| MariaDB's starters: a time machine for 50 articles and RAG over S | same stack and data | they stop at "(to do)", with no sentence level and no vectors over history | SVT and RAG READMEs |
| AntiLeakBench (ACL 2025): benchmarks free of contamination, built from updated knowledge | a "Wikipedia changed its mind" benchmark | builds benchmarks, no reader tool. Whether it uses Wikipedia revisions is **(unverified)** | https://arxiv.org/abs/2412.13670 |
| Wikimedia's Automated Verifiability Checks and the "Verify claim" card in VisualEditor (English Wikipedia, 2026) | model fact checking for editors | checks whether a cited source supports a current claim, nothing on removed claims | https://phabricator.wikimedia.org/T414816, https://phabricator.wikimedia.org/T426359 (from an earlier note, not fetched again) |

One web search for a tool that flags model answers resting on claims later removed from Wikipedia found **no such tool**. The nearest hits were CLAIRE, AntiLeakBench and the retracted papers study. That is one search and proves nothing.

## 4. Risks

### What will not work by Sunday 10:00

- **Embedding all 1,052,406 sentences on the laptop.** At the measured 22.5 sentences a second that is about 13 hours on a laptop that runs hot. A Verda batch job needs credits we do not know and setup time. Embedding only the demo articles (50 to 200 articles, about 10,000 to 40,000 sentences) takes 8 to 30 minutes **(inference)**. Without Verda the scale claim rests on SQL over all lifetimes plus vectors for a subset.
- **A clean splitter over all of M.** The pass cost 2,732 CPU seconds, so about 45 minutes on one core with little memory when streamed **(inference)**. Otherwise the counts stay marked as before the fix.
- **Claim splitting plus a judge with measured precision.** A gold set of 30 pairs plus a judge prompt is half a day. The Nemotron free tier allows about 40 requests a minute per key.
- **A leaderboard over four models.** Cut to one or two.
- **Pageviews, rescue from Swedish and English, live EventStreams, a browser extension, bitemporal periods.** All cut.
- **The index with `AS OF` at a million rows.** HNSW walks the whole graph of current and history rows and the period filter comes after. When few rows match (`AS OF` 2008, say) `LIMIT k` can return fewer than k **(inference, not tested above 3,999 rows)**. Raise `mhnsw_ef_search`, take 50 and filter or restrict by `page_id` first.
- **Partitioning** does not combine with the vector index. Use `KEY(page_id,row_start)`.
- **Schema changes after the load** are blocked on versioned tables. Fix the schema first, reload from the life files if needed.
- **Removed is not false.** The Hennala case shows it. Labels say "Wikipedia stopped saying", show the edit comment and the old version and never say "false".
- **Unchecked headline numbers.** Re-derive 144,711, 78,978, 1,948 and the rank 12 of 148 into saved files before the video. Otherwise drop them.

### CPU and memory

- The build laptop has 16 threads and 60 GB of memory (42 GB free at the time of the check) with 270 GB of free disk.
- The old loader peaked at 11.1 GB per process and eight at once took about 46 GB. The streaming loader peaks at 0.27 GB. Rule: streaming only, one process, no `xargs -P`.
- `candidates.py` reads a whole life file into memory per run (`life-01.jsonl` is 68 MB of JSON) and overwrites `candidates.json`. Change the output path before running it again and run one file at a time.
- bge-m3 through Ollama is the hot part. Keep batches small and embed only the demo set.
- An `article` table with all versions would need 5 to 7 GB (DS README) and the claim vectors 1,052,406 × 4,096 bytes = 4.3 GB before the index. On a laptop, load a subset.
