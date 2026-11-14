# Zombie Facts

*We find claims in AI answers that Wikipedia removed years ago.*

Junction 2026, Attention Is All We Have, MariaDB challenge "Wikipedia Through Time", plan v1, 14 November 2026

## In one minute

In the Finnish history articles of the challenge dataset alone, 223,693 sentences that had stood for at least a year were later removed. For 6,399 of them the edit comment says unsourced, wrong or speculative. A language model trained on an older copy of Wikipedia never hears about it. It can keep repeating the removed claim and the reader has no way to tell.

Zombie Facts keeps the life of every sentence in the Finnish history articles of the challenge dataset: when it appeared, when it disappeared and what the editor wrote in the edit comment. That life is the system time of a row in MariaDB. Dead sentences are history rows of the same table, with a vector next to each one. Paste an AI answer (or let us ask a model) and every claim in it gets one of four labels: **Wikipedia says this**, **Wikipedia stopped saying this**, **Wikipedia contradicts this** or **Wikipedia never said this**. A dead match shows the date, the edit comment and a link to the old version.

It is a side project. Validio, our main project for Valio Aimo, is finished, so this plan is cut to about 20 hours of work until Sunday 10:00, on data the spike on Friday night already built. Citation Lost, the idea we had before, is now one tab of it: sentences that are still in the article but lost their source.

## What MariaDB asks for and our answer

The challenge asks for "a tool for Wikipedia that doesn't exist yet" with "MariaDB at the core of your stack". Its insight paragraph says that language models have "a particular world view" from their training data, which "may differ from Wikipedia's world view". It names "fact-checking assistants" and "time-travel" tools among the things MariaDB would like to see.

| What the challenge asks | Weight | Zombie Facts |
|:---|:---|:---|
| Effective and creative use of MariaDB RAG and/or system-versioned tables | 20 % | a sentence's life on Wikipedia is the row's system period. Dead claims are found with `FOR SYSTEM_TIME ALL` and `VEC_DISTANCE_COSINE` in the same statement |
| Technical execution and scalability across the provided datasets | 20 % | the lifetimes of all 1,052,406 sentences of dataset M go into one system versioned table. Vectors cover a demo set first, the rest is a stretch (see "Build plan") |
| Real-world usefulness for Wikipedia readers or editors | 20 % | readers check an AI answer. Editors get a queue of claims that were removed as unsourced or wrong. They also see living sentences that lost their source |
| Design and demo quality | 20 % | one check page, a time slider, the graveyard and the SQL under every result |
| Originality | 20 % | we found no tool that checks a text against what Wikipedia **removed** (see "The problem") |
| Added technical ambition for SVT or both tracks | 0 %, "recognised" | both tracks in one query |

Everything sits in one MariaDB server: the sentence lives, the vectors and the recorded checks.

## The problem, explained with Wikipedia's own data

We split all 862,076 versions of the 19,742 articles in dataset M into sentences and followed each one through time. Every number below comes from that run.

**Wikipedia forgets a lot.** Of 1,052,406 distinct sentences (counted per article), 479,944 are in the articles today and 572,462 are gone. 223,693 of the gone ones had lived at least one year. 78,978 of those have no reworded twin among the living sentences, so the statement itself left the article and not only its wording.

**Many of them were removed on purpose.** 6,399 of the long lived dead sentences, in 1,470 articles, died in an edit whose comment says something like unsourced (lähteetön), error (virhe), wrong (väärä), speculative or rumour. 4,925 of them had stood for two years or more. Three real cases:

- *Saamelaiset* (the Sámi). "Tähän kuului myös oletus saamelaisten valtaosin mongolidisesta perimästä", a claim about a mostly Mongoloid ancestry, stood 9.8 years. It was removed on 10 October 2020 with the comment "Poistettu kaksi lähteetöntä ja varsin spekulatiivista kappaletta" (two unsourced and rather speculative paragraphs removed).
- *Suomen 1990-luvun alun lama* (the early 1990s depression). "Se ei kuitenkaan ollut niin paha kuin 1930-luvun lama", it was not as bad as the depression of the 1930s, stood 2.3 years and was removed on 27 May 2008 as "lähteetön väite" (unsourced claim). Today the article says GDP fell more steeply in the 1990s than in the 1930s.
- *Hennalan vankileiri* (the Hennala prison camp, 1918). A sentence saying that more than 500 prisoners were shot, about 200 of them women, was removed on 18 May 2018 by an editor who rewrote the article from documents in the National Archives.

**AI models still say these things.** We asked a local Gemma model (gemma3:12b, temperature 0) about the 1990s depression. It answered that the depression "was considerably milder than the Great Depression". That is the claim Wikipedia removed in 2008 and that today's article contradicts. We found it on the first try.

**Plain vector search is not enough.** Matched as a whole, Gemma's long sentence put the dead claim only at rank 12 of 148 (cosine distance 0.479). Restated as one short claim ("The 1990s depression in Finland was not as bad as the depression of the 1930s.") the dead claim came first at 0.268, the next one at 0.437. So the answer is split into short claims first, then vectors find candidates and a language model judges each pair.

**Sources go missing too.** 8,073 of the 479,944 living sentences once carried a `<ref>` and carry none today. That is a lower bound, because a sentence edited in the same step gets a new hash and is not counted. This is Citation Lost and it becomes one tab of Zombie Facts.

We know of three related things. WikiFactDiff compares Wikidata snapshots of 2021 and 2023 and is a dataset, not a tool. Wikimedia's own verifiability checks ask whether a cited source supports a claim. MariaDB's starter repos show one article as it stood on a date (50 articles loaded) and one vector per article for search. None of them looks at what Wikipedia removed. *Prior art was checked with one web search on Friday and needs a second look (open).*

## How Zombie Facts works

| Part | What it does |
|:---|:---|
| **Sentence lives** | every sentence of every version in dataset M, with birth, death, the editor's comment and whether it ever had a source. One row per life in a system versioned table, written with Wikipedia's real times |
| **Claim vectors** | the same rows for a demo set of articles, with a bge-m3 vector (1024 numbers) and a vector index. Living and dead rows share the index |
| **Claim splitter** | a language model turns an answer into short single claims, because short claims match far better (see above) |
| **Two lookups** | for each claim, the nearest living sentences and the nearest dead ones, each in one SQL statement, optionally `AS OF` a date |
| **Judge** | a language model reads each pair and says same, contradicts or unrelated. Vectors only find candidates and never decide |
| **Labels** | says this, stopped saying this, contradicts this, never said this. A dead match always shows the date, the edit comment and the old version |
| **Time slider** | runs the same check `AS OF` an earlier date: "in 2007 this answer was Wikipedia's view" |
| **Graveyard** | long lived claims removed as unsourced or wrong, sorted by how long they stood. An editor's to do list |
| **Citation Lost** | living sentences that lost their source. The same table, one filter |

Removed is not the same as false. Zombie Facts never says "false". It says "Wikipedia stopped saying this" and shows why, in the editor's own words.

## What the user sees

Zombie Facts has one small web page with four tabs, served by the same process as the API. Everything runs on the laptop without a network once the recorded answers are in.

| Screen | What it shows |
|:---|:---|
| Check | a text box with an AI answer, the claims it was split into, one label per claim. A zombie label opens a card with the dead sentence, its life, the edit comment and a link to the old version on fi.wikipedia.org |
| Time slider | the same answer checked `AS OF` a chosen year, labels change colour as the year moves |
| Graveyard | removed claims with their lifetime and edit comment, filter by article and by reason (unsourced, error, speculative) |
| Citation Lost | living sentences that lost their source, with the version where the reference went missing |
| SQL | under every result, the statement that produced it and how long it took |

Finnish sentences come with a short English gloss from the same model, marked as a machine translation.

## Demo in two minutes

Scene: a student asks an AI model about Finnish history for an essay. The answer sounds right. Zombie Facts shows which parts Wikipedia let go of years ago.

1. **The hook (0:00).** One line on screen: "Wikipedia removed this claim in 2008. AI still says it."

2. **Check (0:15).** Gemma's recorded answer about the early 1990s depression goes into the check page. It is split into claims. One claim turns into a zombie: fi.wikipedia said it from 2006 to 2008, an editor removed it as "unsourced claim" and today's article says GDP fell more steeply in the 1990s. A click opens the 2008 version.

3. **Time slider (0:45).** We move the slider to 2007. The same claim turns green: back then this answer was Wikipedia's view. Back to today, it is a zombie again.

4. **Graveyard and Citation Lost (1:05).** The list of claims removed as unsourced or wrong, longest lived first. The Sámi ancestry claim stood 9.8 years. The Citation Lost tab shows 8,073 living sentences whose source disappeared.

5. **Under the hood (1:30).** The SQL of scene 2 on screen: one statement with `FOR SYSTEM_TIME ALL` and `VEC_DISTANCE_COSINE`. Then the scale line: 862,076 versions, 1,052,406 sentence lives in MariaDB, the query time from the final run.

6. **For editors (1:50).** "Bring it back with a source or leave it buried."

The answer in scene 2 is recorded before the demo. The screen says so and names the model and the date.

## Side quests

| Side prize | How Zombie Facts uses it |
|:---|:---|
| Gemma | the model under test in the demo (gemma3:12b, local) and the default splitter and judge |
| Nemotron | optional judge over its API. Its text names about 40 requests a minute per key, so pairs go in batches |
| Verda | only if we embed all of dataset M on a rented GPU. Its text says "Embed MariaDB's full Wikipedia dataset with batch jobs". Not in the small plan |
| Gemini | optional second model under test. We do not claim it unless it does real work |

Whether one team can enter side prizes with two projects is open, because Validio already uses Gemma and Gemini.

## How it works inside

First one check goes through the system from start to end, then each part is explained on its own. Where the plan has not fixed a detail yet it says what we use today and marks it as *our choice*.

### One check from start to end

1. The user pastes an answer or picks a recorded one. Optionally they choose a date for the time slider.

2. The splitter turns the answer into short claims, one fact each, in the answer's language. bge-m3 is multilingual, so an English claim can match a Finnish sentence.

3. Each claim is embedded with bge-m3, the model of the dataset's own article vectors.

4. MariaDB answers two questions per claim. The nearest living sentences:

   ```sql
   SELECT page_id, h, text, VEC_DISTANCE_COSINE(emb, VEC_FromText(?)) d
   FROM claim ORDER BY d LIMIT 8
   ```

   and the nearest dead ones, from the history rows of the same table:

   ```sql
   SELECT page_id, h, text, row_start, row_end, died_rev, died_comment,
          VEC_DISTANCE_COSINE(emb, VEC_FromText(?)) d
   FROM claim FOR SYSTEM_TIME ALL WHERE row_end < NOW() ORDER BY d LIMIT 8
   ```

   With the time slider, the first query reads `FOR SYSTEM_TIME AS OF` the chosen date and the second one only rows that ended before it.

5. The judge gets the claim and its candidates in one call and says for each pair whether it states the same, contradicts or is unrelated.

6. The label follows from those answers (see "Labels"). The check, its claims, the candidates and the labels are stored, so the page and the demo can replay them.

### What we take from the dataset

Dataset M has every saved version of the 19,742 articles up to 1 October 2026 as raw wikitext. The spike streamed it file by file (`iter_batches`, 0.27 GB of memory instead of 11.1 GB) and wrote one life record per sentence and article: text, hash, birth time and version, every death with time, version, editor and comment, seconds alive and whether it ever had a `<ref>`. That took 2,732 CPU seconds for all 16 files. The output is the 16 `life-NN.jsonl` files (530 MB) and `candidates.json` with the 6,399 removed claims from "The problem".

The splitter has known noise. Finnish ordinal dates ("12. maaliskuuta") split a sentence in two, link fragments like `[[Hankoniemi|` leak through and interwiki lines such as `ar:...` look like sentences. The counts above are from before any fix. The loader drops interwiki lines. Whether we fix the rest and rerun is an open decision (see the end).

### Sentence lives in MariaDB

The life records go into `claim_life`, a table `WITH SYSTEM VERSIONING` whose period is the sentence's life on Wikipedia. With `system_versioning_insert_history` the loader writes Wikipedia's own times into `row_start` and `row_end`, so the application never keeps a "valid from" column. The starter repo uses the same switch for 31,848 versions of 50 articles.

The life records keep the first birth and every death but not when a sentence came back. A sentence that died and returned is therefore stored as one life from its first birth to its last death. If it is in the article today it counts as living. This is *our choice* for the small plan and the page says so.

### Claim vectors

`claim` has the same columns plus `emb VECTOR(1024) NOT NULL` and `VECTOR INDEX(emb) M=16 DISTANCE=cosine`. It holds the demo set only: the 100 articles with the most removed claims in `candidates.json` and the four articles of the spike (*Hangon vuokra-alue*, *Hennalan vankileiri*, *Saamelaiset*, *Suomen 1990-luvun alun lama*). It takes living sentences and those that died after at least one year. For the 100 articles that is 30,167 sentences, for the four articles 750, minus any overlap.

The spike showed that this works. A vector index on a system versioned table accepts history rows written with `insert_history` and `EXPLAIN` shows the index used for current rows and for `FOR SYSTEM_TIME ALL`. On 3,999 sentences of 66 articles the index found the same top 10 as an exact search in 99.7 % of cases for current rows and in all cases `AS OF` 2012 and over all rows. It took 0.8 to 1.3 ms against 84 to 273 ms for the exact search. We keep the starter repo's lessons: `KEY(page_id,row_start)` for `AS OF`, `mhnsw_ef_search=80` and the vector search kept in a subquery so the index is used.

### Splitter and judge

Both are prompts to the same model with a fixed JSON answer. The splitter returns a list of claims of at most about 20 words. The judge gets one claim and up to 16 candidates and returns `same`, `contradicts` or `unrelated` for each. Up to 10 claims go into one call to stay under rate limits. The default model is gemma3:12b on the laptop through Ollama (*our choice*, it is already pulled and measured). Both have a fake twin that answers from a fixed file, so tests and the demo run without a model.

### Labels

| Label | When it is given |
|:---|:---|
| says this | a living sentence states the same |
| says this, source lost | as above, but the sentence lost its `<ref>` (Citation Lost) |
| stopped saying this | a dead sentence states the same and no living sentence does |
| contradicts this | a living sentence contradicts the claim, whether or not a dead one supports it |
| never said this | no candidate is judged the same or contradicting |

"Contradicts" wins over everything else. A zombie that today's article contradicts gets both on its card, as in the depression case. Distance alone never gives a label: in the spike the Hennala answers sat at 0.37 to 0.47 from their nearest sentences, right and wrong ones alike.

### Graveyard and Citation Lost

Both are plain SQL over `claim_life` and need no vectors. The graveyard is `FOR SYSTEM_TIME ALL WHERE row_end < NOW()`, filtered to deaths whose comment matches the words from the spike (lähteetön, virhe, väärä, poist, spekul, huhu, POV) and sorted by lifetime. Citation Lost reads living rows with `ref_ever` set and `ref_now` not set. Both link to the version where the change happened.

### Data model

| Where | Tables |
|:---|:---|
| sentence lives, all of M | `claim_life` (system versioned, no vector) |
| demo set | `claim` (system versioned, VECTOR(1024) with index), `article` (page id, title, latest version) |
| checks | `check_run` (answer, model, date, recorded or live), `check_claim` (claim, label, chosen candidates, judge output) |

Everything is in one MariaDB 12.3.3 server in Docker (`mariadb:lts`) on 127.0.0.1.

### API

| Route | Input | Output |
|:---|:---|:---|
| `POST /api/check` | text, optional date | claims with labels, candidates and the SQL that ran |
| `GET /api/check/{id}` | check id | a stored check, for replay |
| `GET /api/graveyard` | article, reason, limit | removed claims with lifetime and comment |
| `GET /api/citation-lost` | article, limit | living sentences that lost their source |
| `GET /api/health` | | database and model status |

### Repo layout

| Folder | What is in it |
|:---|:---|
| `zombie-facts/src/zombiefacts/` | load, embed, split, lookup, judge, api, demo |
| `zombie-facts/web/` | the static page with its four tabs |
| `zombie-facts/scripts/` | the spike's sentence pass, the loaders, the demo check |
| `zombie-facts/data/` | local only, never committed: life files, vectors, recorded answers |

The folder sits next to `validio/` in the team repo. The package name `zombiefacts` is *our choice*.

## Build plan

GLaDOS builds everything, in the order below. A step counts as done only when its acceptance test passes. The machine runs hot, so there is never more than one heavy job at a time (embedding, a model run, a full load) and long passes stream file by file, never `xargs -P`. Progress goes to #general at every checkpoint. If a checkpoint is missed, the cut list below decides what goes.

### Stack

| Layer | What we use |
|:---|:---|
| Database | MariaDB 12.3.3 in Docker (`mariadb:lts`), as in the spike |
| Backend | Python 3.12 with uv, FastAPI and uvicorn, pymysql, pyarrow for the dataset |
| Vectors | bge-m3 through Ollama on the laptop, 1024 dimensions, cosine |
| Splitter and judge | gemma3:12b through Ollama, with a fake twin for tests and the demo |
| Web page | one static HTML page with plain JavaScript, served by FastAPI |
| Tests | pytest, Playwright for the click-through and screenshots |
| Hosting | one process on 127.0.0.1 for the demo. No public link in the small plan |

Every risky part already ran in the spike on Friday night: real timestamps with `insert_history`, a vector index on a system versioned table, `AS OF` combined with vector search, the sentence pass over all of M and a model answer that repeated a dead claim.

### Data we seed

`make demo` always starts from the same state, so every run shows the same numbers.

- **Sentence lives** for all of M from the spike's life files.
- **Claim vectors** for the demo set from "Claim vectors", embedded once and kept as a file, so a reset never embeds again.
- **Recorded answers**: 20 questions written from removed claims in `candidates.json`, the depression question of the spike among them, asked once to gemma3:12b at temperature 0. Answers, claims and labels are stored with model and date and shown as recorded.
- **Gold set**: 30 claims from those answers with their candidates, labelled by hand, to measure how often the labels are right.

### Steps, checkpoints and acceptance tests

Times are wall time from about 10:00 on Saturday. Lane A is code. Lane B is the one heavy background job, which never overlaps with another.

| # | Step | Lane | Time | Acceptance test |
|:---|:---|:---|:---|:---|
| 1 | Skeleton: folder, Makefile, MariaDB in Docker on 127.0.0.1, `/api/health`, a guard check for keys and home paths | A | 30 min | health answers. The guard fails on a planted key and passes on a clean tree |
| 2 | Load `claim_life` from the 16 life files, one file at a time | B | 60 min | rows equal the life records minus the dropped interwiki lines, with that number printed. Current rows match the living count. *Alueen luovutuksen yhteydessä noin 8 000 suomalaista menetti kotinsa* shows 3,933 days, died 22 March 2017 |
| 3 | Embed the demo set with bge-m3 and load `claim` | B | 40 min | about 31,000 rows (about 23 min at the spike's 22.5 sentences per second). Index search finds the same top 10 as exact search in at least 99 % of 30 probes. `EXPLAIN` shows the index |
| 4 | Graveyard and Citation Lost queries | A | 30 min | the Sámi claim shows 9.8 years and its comment. Citation Lost over all of M counts 8,073 (any difference is explained) |
| | **Checkpoint 1, about 12:30:** the data is in MariaDB | | | |
| 5 | Splitter with fake twin | A | 40 min | Gemma's depression answer yields a claim that finds the dead 2008 sentence at rank 1 |
| 6 | Two lookups, with `AS OF` | A | 30 min | for that claim the dead lookup returns the 2008 sentence. `AS OF` 2007 returns it as living. Each query is under 10 ms on the demo set |
| 7 | Judge with fake twin, labels | A | 45 min | the depression claim is labelled stopped saying this and contradicts this. Contradicts wins over everything |
| 8 | Record the 20 answers and run the checks once | B | 60 min | 20 stored checks. `make demo` runs with Ollama stopped |
| 9 | Gold set of 30 claims, labelled by hand | A | 60 min | precision and recall of "stopped saying this" written to a file, whatever they are |
| | **Checkpoint 2, about 17:00:** scene 2 works in plain Python and we know how good the labels are. Headline decision here | | | |
| 10 | API | A | 40 min | `POST /api/check` with the depression answer returns the labels and the SQL in replay mode |
| 11 | Web page: Check and the claim card | A | 90 min | screenshots at 1280 and 390 pixels looked at. The old version link opens the right revision |
| 12 | `make demo-check` | A | 30 min | `ALL SCENES OK` for scenes 2 and 4, twice in a row from a reset |
| | **Checkpoint 3, about 21:00:** check, graveyard and SQL run end to end. This is the minimum we can show | | | |
| 13 | Time slider | A | 45 min | the depression claim is green `AS OF` 2007 and a zombie today. Scene 3 passes the demo check |
| 14 | Graveyard and Citation Lost tabs, SQL panel | A | 60 min | one Playwright test per scene clicks through it |
| | **Checkpoint 4, about 01:00 on Sunday:** all scenes can be clicked through | | | |
| 15 | README, deck, video | both | 3 h | the README commands work in a fresh clone. The video shows all scenes and stays under two minutes |
| 16 | Submission | | 30 min | done by 09:30 |
| 17 | Second model under test (Nemotron or Gemini) | B | optional | only if everything above is done |
| 18 | Embed all of M | B | optional | about 8.7 hours for 703,637 sentences at the spike's rate. Only overnight on a cool machine or on a rented GPU |

Feature freeze is Sunday 05:00. After that only the README, the deck and the video.

### Demo script, tied to the steps

| Scene | What the audience sees | Built in steps |
|:---|:---|:---|
| 1. Hook (0:00) | one line: "Wikipedia removed this claim in 2008. AI still says it" | 15 |
| 2. Check (0:15) | Gemma's recorded answer, its claims, one zombie card with dates, comment and the old version | 2, 3, 5 to 11 |
| 3. Time slider (0:45) | the claim turns green at 2007 and back to a zombie today | 6, 13 |
| 4. Graveyard and Citation Lost (1:05) | the Sámi claim at 9.8 years, 8,073 sentences that lost their source | 4, 14 |
| 5. Under the hood (1:30) | the SQL of scene 2 and the scale line | 2, 14 |
| 6. For editors (1:50) | the closing line | 15 |

The click-through runs with `make demo` on the laptop and with the recorded answers, so the venue's network and the machine's temperature cannot break it. `make record` drives the same path with Playwright and writes the video.

### Timeline

Saturday 10:00 to 12:30 data, until 17:00 the check in Python, until 21:00 the minimum demo, until 01:00 all scenes. Sunday until 05:00 polish, until 09:30 video and submission.

### Risks and fallbacks

| Risk | How we notice | What we do |
|:---|:---|:---|
| The labels are often wrong | the gold set in step 9 | report the number honestly. If it is poor, the headline becomes the graveyard and Citation Lost, which need no model |
| Removed is read as false | a judge asks | the page never says false. It shows the editor's comment and the old version every time |
| The machine overheats during embedding or a model run | fans, throttling, slow steps | one heavy job at a time. Embedding writes to a file and resumes where it stopped. The demo needs no heavy run |
| Splitter noise inflates the counts | odd sentences in the graveyard | drop interwiki lines at load. Say on the page that the counts come from a simple splitter. A rerun with fixes is open |
| `AS OF` with a vector index returns fewer than k rows at large sizes | a lookup returns too few rows | not tested beyond 3,999 rows. Raise `mhnsw_ef_search` or fetch 50 and filter. Last resort: living and dead in two tables |
| Loading all of M takes too long | step 2 runs over two hours | load the life records of the demo set first and the rest in the background |
| The demo answer changes | a new run gives other words | the demo uses the recorded answer. A live run is a switch |
| Simulated or partial parts look complete | a judge asks | the page says which answers are recorded and how many articles have vectors |

**Cut list, first to go first:** the second model, embedding all of M, the Citation Lost tab (its number stays in the graveyard), the time slider, the SQL panel (the SQL goes into the video instead), the gold set beyond 15 claims.

**Never cut:** the sentence lives in a system versioned table, dead claims found by vector search in the same table, the judge, the dead claim card with comment and old version, the depression case and `make demo-check`.

## Decided and still open

- **Wording:** "stopped saying" and "contradicts", never "false".
- **Data:** dataset M as shipped and the spike's life files. Nothing from Wikipedia live except links to old versions.
- **Licence:** Wikipedia text is CC BY-SA, so the page names fi.wikipedia.org as the source of every sentence it shows.
- **Git:** the work goes into `zombie-facts/` in the team repo. GLaDOS keeps `main` passing the demo check.
- **Open:** whether the team can submit a second project to the MariaDB challenge and side prizes next to Validio.
- **Open:** fix the splitter and rerun the sentence pass with real rebirth times (about 46 CPU minutes, one file at a time) or keep the spike's output.
- **Open:** gemma3:12b on the laptop as judge or Nemotron over its API.
- **Open:** who labels the 30 gold claims. They are Finnish sentences.
- **Open:** embed all of M overnight or keep vectors on the demo set.
- **Ask MariaDB mentors on Saturday:** a teammate heard on Friday that "vector search is not being used". We want to know whether they want vector search, system versioned tables or both in the same query.

## Short glossary

- **System versioned table**: a MariaDB table that keeps every earlier state of each row with the time it was valid. `AS OF` reads it as it stood on a date.
- **History row**: a row that is no longer current. Here it is a sentence that left the article.
- **Vector search**: finding sentences with a similar meaning by comparing lists of numbers (vectors) a model computed for each one.
- **Zombie**: a claim Wikipedia removed that still turns up in an AI answer.
- **Judge**: a language model that reads two sentences and says whether they say the same, contradict or are unrelated.
- **Old version (oldid)**: a fixed link to one saved version of a Wikipedia article.

Sources: challenge text c-307, MariaDB's dataset and starter repos (READMEs read on 13 November 2026), challenge texts c-46 and c-56 for the side prizes, our own spike on the night of 13 November (sentence pass over all of dataset M, MariaDB tests, Gemma probe), our idea evaluation of the same night. Prepared with Claude Opus 5.5.
