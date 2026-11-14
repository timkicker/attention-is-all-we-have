# Parallax build plan

Build plan for our entry to MariaDB's challenge "Wikipedia Through Time" (Junction 2026, c-307). Written Saturday 14 November at about 15:30 Helsinki time. Final submission is **Sunday 15 November 10:00**. All times below are Helsinki time.

Two people build in parallel, each with their own AI coding agents: **Track A "data and engine"** and **Track B "app"**. Abdallah and his teammate decide between themselves who takes which track. Tim writes the contract with his agent GLaDOS before the tracks start, merges at the merge points and records the video.

This file is the only briefing the coding agents get. Every task below carries what it needs. If something here contradicts the code in `parallax/contract/`, the contract wins and the agent tells its human.

## 0. Product

### In ten lines

1. Parallax lines up what seven Wikipedia language editions (fi sv de en ru et uk) say about one topic, the Winter War, claim by claim.
2. One date slider cuts every edition at the same instant with MariaDB's `FOR SYSTEM_TIME AS OF`.
3. Claims are sentences. Each sentence life is one row of a system-versioned table whose period is the time Wikipedia stated it.
4. A bge-m3 vector on that same table finds the matching sentence in another edition, in one SQL statement together with `AS OF`.
5. Gemini (`gemini-3.8-flash`) judges each candidate pair (same, partial, contradicts, different) and marks differing numbers and terms.
6. "Dropped here, alive there" lists claims one edition removed while other editions still state them, with the date, the edit comment and the old revision.
7. "Check an answer" splits a pasted AI answer into claims and labels each per edition: says, stopped saying, contradicts, not found.
8. Breadth comes from MariaDB's datasets: every revision of 19,742 Finnish articles (M) as sentence lives and an atlas of 2,919 topics in fi, sv and en (S).
9. "Under the hood" shows the SQL behind every panel with its time and row count.
10. The tool only shows evidence. A person decides and edits on Wikipedia. Parallax never writes to Wikipedia.

### Demo script (2:00)

The demo opens with the cross-language comparison through time (decision Q1). We record a video of it. The live demo runs on the shared instance and falls back to fake mode with recorded answers if the network fails (Q14).

| Time | Screen | What is said or shown |
|---|---|---|
| 0:00 | Title card, wordmark "Parallax" | "Same war, seven Wikipedias. What does each one say and when did that change?" |
| 0:08 | Compare, Winter War, anchor fi, today | Rows for the start of the war, Mainila, Finnish dead and the territory ceded. Number cells marked "differs": Finnish dead 26,662 fi, 22,830 sv, 25,904 en ru et uk; territory 9 % en, 13 % et. Mainila verbs: fi "lavasti" (staged), de "inszenierte" (staged), sv "kunnat bevisas" (proven), en "reported" plus "false flag", ru "по заявлению советской стороны" (by the Soviet side's account). Each match carries a verdict chip from the Gemini judge |
| 0:30 | Time slider dragged from 2006 to today | en Mainila cell changes from "the Soviets staged" to "an incident was reported" on 21 Aug 2009 (rev 309285088, comment "rewrote the mainila incident part to correspond with the article"). ru loses "инсценированный советской стороной" (staged by the Soviet side) on 9 Jul 2014 (rev 64106894). Life bars per edition under the row |
| 0:55 | Dropped here, alive there | The ru clause dropped in 2014 while de, fi and sv still say the incident was staged. Click opens ru `?oldid=63917953`. Then the Finnish scale line: lives from 862,076 revisions, filter "unsourced" (lähteetön) |
| 1:15 | Check an answer | A recorded answer (model and date on screen) about the Mainila shots. Each claim gets one chip per edition. One claim reads "en: stopped saying (2009)", another "not found in et". Gemini is named as the judge, with its measured agreement on our gold set |
| 1:35 | Under the hood | The one statement with `FOR SYSTEM_TIME AS OF` and `VEC_DISTANCE_COSINE`, its milliseconds and rows. Scale line: rows, distinct sentences, vectors, the Verda GPU throughput |
| 1:50 | Footer and an "open on fi.wikipedia" button | "Evidence, not edits." The button opens the section on Wikipedia. Footer: not affiliated with the Wikimedia Foundation, CC BY-SA |

### Rules for every task

Every agent applies these in every commit. `make check-rules` tests the ones a script can find.

- **Assistant only.** No write call to any Wikimedia API, no OAuth, no bot, no edit button, no generated article text. Buttons only open a page or section on the real Wikipedia.
- **Neutral wording.** The UI says "differs", "not found in", "uses the term", "cites mostly", "stopped saying". Never "biased", "propaganda", "false", "wrong", "lie" or any ranking or score of editions. No editor names anywhere in the UI. Both sentences are always visible. Glosses are labelled "machine translation".
- **No Wikipedia look-alike.** Codex 2.7.0 tokens and components, our own layout and our own text wordmark. No puzzle globe, no Wikipedia wordmark, no `cdxIconLogo*` icon, no Vector header, sidebar or Read/Edit/View history tabs, no "From Wikipedia, the free encyclopedia". No "Wiki" or "pedia" in the product name, the page title or a domain.
- **Footer on every page:** "Independent hackathon project. Not affiliated with or endorsed by the Wikimedia Foundation. Wikipedia is a trademark of the Wikimedia Foundation. Text from Wikipedia under CC BY-SA 4.0, split into sentences." Every quoted sentence links to its `?oldid=`.
- **Polite client.** Every Wikimedia request sends `User-Agent: Parallax/0.1 (https://github.com/timkicker/attention-is-all-we-have) python-requests/<version>`. One request at a time by default, never more than 3 in parallel, honour `Retry-After` on 429 (else wait 5 s and double), `maxlag=5` on Action API calls. Every response is cached on disk under `parallax/data/raw/` and never fetched twice.
- **No secrets in git.** Keys go in `parallax/.env` (gitignored). `parallax/.env.example` lists the names with empty values. No API key in logs, issues, Discord or fixtures.
- **No personal data.** No Wikipedia user names are stored or shown. The M dataset's `user` column is never read.
- **Commits:** one line, lowercase, 2 to 5 words, no body, no trailer. Examples: `add wikitext parser`, `fix compare null cells`.
- **Tests for each step.** A task is done when its done check passes and its tests are committed. Status messages in Discord follow WORKING.md (`DONE:` only with the command that passed).
- **No home paths.** No repo file contains an absolute path into a user's home directory. Paths are relative to `parallax/`.
- **Licence.** The repo stays MIT. Codex is never copied into the repo or the built bundle: the browser loads it unchanged from jsDelivr through an import map.

## 1. Contract phase

**Who:** Tim with GLaDOS, on `main`, 15:45 to 16:45. Meanwhile Abdallah and his teammate set up their laptops (Docker, `uv`, Node 22, `gh` logged in with access to the repo) and Track A's human submits the Verda credits form (Junction Hackerpacks). Tim sends each of them the Gemini API key by DM; it goes into their own `parallax/.env` and nowhere else.

**Branches:** `track-a` and `track-b` start from the commit that adds this plan. When the contract lands on `main` (about 16:45), each track runs `git merge main` into its branch. Nobody force-pushes.

### Files

All paths are relative to the repo root.

| File | Content |
|---|---|
| `parallax/pyproject.toml`, `uv.lock` | One Python 3.12 project for all tracks. Packages `contract`, `pipeline`, `engine`, `eval`, `api` at the top of `parallax/`. Dependencies declared once: fastapi, uvicorn, pymysql, numpy, pyarrow, mwparserfromhell, requests, openai, pyyaml, pytest, httpx, ruff (`openai` is also the Gemini client, through Gemini's OpenAI-compatible endpoint); optional group `gpu` with sentence-transformers and torch. New dependencies only through Tim on `main` |
| `parallax/.env.example` | `DB_HOST=127.0.0.1`, `DB_PORT=3307`, `DB_USER=parallax`, `DB_PASSWORD=`, `DB_NAME=parallax`, `ENGINE=fake`, `GEMINI_API_KEY=`, `EMBED_BACKEND=ollama`, `EMBED_URL=http://127.0.0.1:11434`, `SEED=v1` |
| `parallax/.gitignore` | `.env`, `data/`, `web/node_modules/`, `web/dist/`, `e2e/results/`, `*.sql.gz` |
| `parallax/docker-compose.yml` | Service `db`: image `mariadb:12.3.3`, port `127.0.0.1:3307:3306`, volume `parallax-db`, config `db/my.cnf`, healthcheck `healthcheck.sh --connect` |
| `parallax/db/my.cnf` | `max_allowed_packet=256M`, `mhnsw_max_cache_size=1073741824`, `secure_timestamp=NO`, `innodb_buffer_pool_size=2G`, `character-set-server=utf8mb4`, `default-time-zone='+00:00'` |
| `parallax/contract/schema.sql` | All tables below, exact columns and indexes |
| `parallax/contract/engine.py` | The engine interface, the fake engine and `get_engine()` |
| `parallax/contract/openapi.yaml` | The HTTP API of section 1.4 with one example response per route |
| `parallax/contract/examples/*.json` | One example response per route, the same as in `openapi.yaml`, used by B's UI tests and by the contract tests |
| `parallax/contract/fixtures/engine/*.json` | Fake engine data: `embed.json`, `split.json`, `judge.json`, `gloss.json` |
| `parallax/contract/fixtures/seed-mini.sql` | About 400 claim rows around Mainila in 6 editions with vectors, plus their sections, revisions and verdicts. Under 3 MB, committed, used by CI |
| `parallax/contract/SEED.md` | Where each seed comes from and how to load it |
| `parallax/Makefile` | Shared targets plus `include pipeline/targets.mk` (owned by A) and `include api/targets.mk` (owned by B). The contract creates both include files with every target name below as a stub that prints `not built yet` and exits 1 |
| `parallax/tests/contract/` | `test_schema.py`, `test_engine_fake.py`, `test_examples.py` |
| `parallax/scripts/check_rules.py` | The guards behind `make check-rules` |
| `.github/workflows/parallax.yml` | On push: `uv sync`, `ruff check`, `make check-rules`, then pytest for contract, pipeline and api against a MariaDB 12.3.3 service container loaded with `seed-mini.sql` |

### 1.1 schema.sql

Constraints this follows: one vector index per table, no partitioning on a table with a vector index, `DISTANCE=cosine` always declared, schema final before the big load (`system_versioning_alter_history=ERROR` is the default). Times are UTC. Every session runs `SET time_zone='+00:00'` and `SET mhnsw_ef_search=1000`.

```sql
-- Parallax schema v1, MariaDB 12.3.3. Change only through a contract commit on main.
CREATE TABLE topic (
  topic_id    VARCHAR(32)  NOT NULL PRIMARY KEY,          -- 'winterwar'; S atlas topics use the Wikidata id
  wikidata_id VARCHAR(16)  NOT NULL UNIQUE,
  label_en    VARCHAR(255) NOT NULL,
  depth       ENUM('deep','atlas') NOT NULL
);

CREATE TABLE page (
  lang     VARCHAR(8)   NOT NULL,
  page_id  INT UNSIGNED NOT NULL,
  topic_id VARCHAR(32)  NULL,
  title    VARCHAR(255) NOT NULL,
  source   ENUM('api','M','S') NOT NULL,
  history  ENUM('every','yearly','none') NOT NULL,
  PRIMARY KEY (lang, page_id), KEY (topic_id)
);

CREATE TABLE revision (                                   -- metadata only, never a user name
  lang      VARCHAR(8)      NOT NULL,
  rev_id    BIGINT UNSIGNED NOT NULL,
  page_id   INT UNSIGNED    NOT NULL,
  parent_id BIGINT UNSIGNED NULL,
  ts        DATETIME(6)     NOT NULL,
  bytes     INT UNSIGNED    NULL,
  minor     TINYINT(1)      NOT NULL DEFAULT 0,
  comment   VARCHAR(1000)   NULL,
  snapshot  TINYINT(1)      NOT NULL DEFAULT 0,             -- 1 if its text was parsed
  PRIMARY KEY (lang, rev_id), KEY (lang, page_id, ts)
);

CREATE TABLE section_text (
  topic_id VARCHAR(32) NOT NULL, lang VARCHAR(8) NOT NULL, section VARCHAR(255) NOT NULL,
  rev_id BIGINT UNSIGNED NOT NULL, n_sent INT UNSIGNED NOT NULL, text MEDIUMTEXT NOT NULL,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (topic_id, lang, section), KEY (topic_id, lang, row_start)
) WITH SYSTEM VERSIONING;

CREATE TABLE claim (                                      -- one row per sentence life, with a vector
  lang VARCHAR(8) NOT NULL, page_id INT UNSIGNED NOT NULL, h CHAR(16) NOT NULL,
  topic_id VARCHAR(32) NULL,
  section VARCHAR(255) NOT NULL, text TEXT NOT NULL,
  born_rev BIGINT UNSIGNED NOT NULL,
  died_rev BIGINT UNSIGNED NULL, died_comment VARCHAR(1000) NULL,
  time_precision ENUM('exact','snapshot') NOT NULL,      -- snapshot: bounds are yearly snapshot times
  has_ref TINYINT(1) NOT NULL DEFAULT 0, had_ref TINYINT(1) NOT NULL DEFAULT 0,
  emb VECTOR(1024) NOT NULL,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (lang, page_id, h),
  KEY (topic_id, lang, row_start), KEY (lang, row_start),
  VECTOR INDEX (emb) M=16 DISTANCE=cosine
) WITH SYSTEM VERSIONING;

CREATE TABLE claim_life_fi (                              -- all M lives, no vectors
  page_id INT UNSIGNED NOT NULL, h CHAR(16) NOT NULL, text TEXT NOT NULL,
  born_rev BIGINT UNSIGNED NOT NULL, died_rev BIGINT UNSIGNED NULL, died_comment VARCHAR(1000) NULL,
  reason ENUM('none','unsourced','error','speculation','other') NOT NULL DEFAULT 'none',
  has_ref TINYINT(1) NOT NULL DEFAULT 0, had_ref TINYINT(1) NOT NULL DEFAULT 0,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (page_id, h), KEY (page_id, row_start), KEY (reason)
) WITH SYSTEM VERSIONING;

CREATE TABLE article_vec (                                -- S article vectors as shipped
  lang VARCHAR(8) NOT NULL, page_id INT UNSIGNED NOT NULL, wikidata_id VARCHAR(16) NOT NULL,
  title VARCHAR(255) NOT NULL, truncated TINYINT(1) NOT NULL, emb VECTOR(1024) NOT NULL,
  PRIMARY KEY (lang, page_id), KEY (wikidata_id),
  VECTOR INDEX (emb) M=16 DISTANCE=cosine
);

CREATE TABLE atlas_topic (
  wikidata_id VARCHAR(16) NOT NULL PRIMARY KEY,
  title_fi VARCHAR(255) NULL, title_sv VARCHAR(255) NULL, title_en VARCHAR(255) NULL,
  coverage ENUM('fi','fi+sv','fi+en','all') NOT NULL,
  dist_fi_sv FLOAT NULL, dist_fi_en FLOAT NULL, dist_sv_en FLOAT NULL,
  topic_id VARCHAR(32) NULL,                              -- set when deep data exists
  KEY (coverage)
);

CREATE TABLE align (                                      -- cached nearest candidates per anchor date
  as_of DATE NOT NULL,
  src_lang VARCHAR(8) NOT NULL, src_page INT UNSIGNED NOT NULL, src_h CHAR(16) NOT NULL,
  dst_lang VARCHAR(8) NOT NULL, rank TINYINT UNSIGNED NOT NULL,
  dst_page INT UNSIGNED NOT NULL, dst_h CHAR(16) NOT NULL,
  dist FLOAT NOT NULL, method ENUM('exact','ann') NOT NULL,
  PRIMARY KEY (as_of, src_lang, src_page, src_h, dst_lang, rank), KEY (dst_lang, dst_h)
);

CREATE TABLE verdict (
  a_lang VARCHAR(8) NOT NULL, a_h CHAR(16) NOT NULL, b_lang VARCHAR(8) NOT NULL, b_h CHAR(16) NOT NULL,
  prompt_version VARCHAR(16) NOT NULL,
  label ENUM('same','partial','contradicts','different') NOT NULL,
  numbers JSON NULL, terms JSON NULL,                     -- [["26 662","25 904"]], [["lavasti","reported"]]
  model VARCHAR(80) NOT NULL, raw JSON NULL, judged_at DATETIME(6) NOT NULL,
  PRIMARY KEY (a_lang, a_h, b_lang, b_h, prompt_version)
);

CREATE TABLE gloss (
  lang VARCHAR(8) NOT NULL, h CHAR(16) NOT NULL, text_en TEXT NOT NULL, model VARCHAR(80) NOT NULL,
  PRIMARY KEY (lang, h)
);

CREATE TABLE term (
  term_id VARCHAR(32) NOT NULL, lang VARCHAR(8) NOT NULL, pattern VARCHAR(255) NOT NULL,
  concept VARCHAR(64) NOT NULL, gloss_en VARCHAR(255) NOT NULL,
  PRIMARY KEY (term_id, lang)
);

CREATE TABLE term_hit (
  topic_id VARCHAR(32) NOT NULL, lang VARCHAR(8) NOT NULL, term_id VARCHAR(32) NOT NULL, h CHAR(16) NOT NULL,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (topic_id, lang, term_id, h)
) WITH SYSTEM VERSIONING;

CREATE TABLE ref_stat (
  topic_id VARCHAR(32) NOT NULL, lang VARCHAR(8) NOT NULL, rev_id BIGINT UNSIGNED NOT NULL,
  refs INT UNSIGNED NOT NULL, isbn JSON NOT NULL, domains JSON NOT NULL,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (topic_id, lang)
) WITH SYSTEM VERSIONING;

CREATE TABLE check_run (
  run_id CHAR(12) NOT NULL PRIMARY KEY, created_at DATETIME(6) NOT NULL,
  input_text MEDIUMTEXT NOT NULL, source ENUM('recorded','live') NOT NULL,
  answer_model VARCHAR(80) NULL, answer_date DATE NULL, question TEXT NULL,
  as_of DATETIME NULL, engine ENUM('fake','real') NOT NULL
);

CREATE TABLE check_claim (
  run_id CHAR(12) NOT NULL, idx SMALLINT UNSIGNED NOT NULL, text TEXT NOT NULL,
  emb VECTOR(1024) NULL, labels JSON NOT NULL,
  PRIMARY KEY (run_id, idx)
);

CREATE TABLE gold_pair (
  a_lang VARCHAR(8) NOT NULL, a_h CHAR(16) NOT NULL, b_lang VARCHAR(8) NOT NULL, b_h CHAR(16) NOT NULL,
  label ENUM('same','partial','contradicts','different') NOT NULL,
  labeller VARCHAR(16) NOT NULL, note VARCHAR(255) NULL,
  PRIMARY KEY (a_lang, a_h, b_lang, b_h)
);

CREATE TABLE stat (                                       -- numbers for the scale line and the docs
  k VARCHAR(64) NOT NULL PRIMARY KEY, v JSON NOT NULL, computed_at DATETIME(6) NOT NULL
);
```

Conventions the schema relies on:

- `h` is `sha1(normalised text)` as 16 hex characters. Normalised means lowercased, Unicode NFC, whitespace collapsed to single spaces and trimmed. Function `contract.engine.claim_hash(text)`.
- A current row has `row_end` at the maximum timestamp. Queries use `AS OF`, `ALL` or `row_end < NOW()`, never a literal end date.
- History rows are written with `SET system_versioning_insert_history=1` and explicit `row_start` and `row_end`. Two lives with the same start get +1 µs.
- `section` is `[lead]`, `[infobox]` or the heading text.

### 1.2 engine.py

```python
# parallax/contract/engine.py  (contract, change only on main)
from dataclasses import dataclass, field
from typing import Literal, Protocol
Label = Literal["same", "partial", "contradicts", "different"]

@dataclass(frozen=True)
class Candidate:
    lang: str
    page_id: int
    h: str
    text: str

@dataclass(frozen=True)
class Verdict:
    h: str                                   # the candidate's h
    label: Label
    numbers: list[tuple[str, str]] = field(default_factory=list)   # (in claim, in candidate)
    terms: list[tuple[str, str]] = field(default_factory=list)
    note: str = ""

class Engine(Protocol):
    name: str                                # "fake" or "real"
    model_id: str                            # judge model id, shown in the UI
    prompt_version: str                      # e.g. "judge-v1"
    def embed(self, texts: list[str]) -> list[list[float]]: ...          # 1024 floats each, L2-normalised
    def split_claims(self, text: str, lang: str | None = None) -> list[str]: ...
    def judge(self, claim: str, claim_lang: str, candidates: list[Candidate]) -> list[Verdict]: ...
    def gloss(self, texts: list[str], lang: str) -> list[str]: ...        # English, same order

def claim_hash(text: str) -> str: ...
def get_engine() -> Engine:
    """ENGINE=fake -> FakeEngine(); ENGINE=real -> engine.real.RealEngine()."""
```

The fake engine is deterministic and needs no network:

- `embed`: if `claim_hash(text)` is in `fixtures/engine/embed.json` (base64 float32), return that vector. Else a unit vector from a NumPy generator seeded with the hash.
- `split_claims`: lookup in `split.json` by hash of the input, else the sentence splitter regex from section 2 (A3).
- `judge`: lookup `(claim hash, candidate h)` in `judge.json`, else `same` if the normalised texts are equal and `different` otherwise.
- `gloss`: lookup `(lang, h)` in `gloss.json`, else the text unchanged with the prefix `[no gloss] `.

The fixtures cover the demo path: three claims about Mainila whose fake vectors are copies of seed rows' vectors (so the Check view finds real rows in fake mode), their judge labels and glosses for every seed-mini sentence shown in the demo.

### 1.3 Seeds

| Seed | Source | Where | Loaded by |
|---|---|---|---|
| `seed-mini.sql` | Cut from seed v1: rows whose section mentions Mainila or the casualties, all 6 editions | committed in `contract/fixtures/` | `make seed-mini`, CI |
| `v1` | The Saturday spike database on Tim's laptop (container `wikispike`, schema `lens`, tables `sentence` with 7,116 rows and `section_text` with 784 rows: Winter War, 6 editions fi sv de en ru et, 6 snapshots each, bge-m3 vectors). GLaDOS converts it into schema v1 (`sentence` to `claim` with `time_precision='snapshot'`, `topic_id='winterwar'`), adds the fixtures' verdicts and glosses and dumps with `mariadb-dump --dump-history` | GitHub release `parallax-seed-v1`, asset `seed.sql.gz` | `make seed SEED=v1` |
| `v2` | Track A at merge point M1: full Winter War, 7 editions | release `parallax-seed-v2` | `make seed SEED=v2` |
| `v3` | Track A at M2: plus verdicts, glosses, M lives, atlas | release `parallax-seed-v3` | `make seed SEED=v3` |
| `final` | Track A at 04:30 | release `parallax-seed-final` | the demo instance |

Releases are made with `gh release create parallax-seed-vN parallax/data/seed.sql.gz --title "seed vN" --notes "<row counts>"` and downloaded with `gh release download`. Data never goes into a commit.

### 1.4 openapi.yaml

B serves this API. A never calls it. Every JSON response also carries `"sql": [{"text": "...", "ms": 1.4, "rows": 7, "index": "emb|none"}]` so "Under the hood" needs no extra work.

| Route | Parameters | Response (shape) |
|---|---|---|
| `GET /api/health` | | `{db, engine, model_id, seed, counts:{claim, claim_life_fi, verdict}}` |
| `GET /api/topics` | | `{topics:[{topic_id, label_en, wikidata_id, depth, editions:[{lang, page_id, title, history, revisions, first_ts}]}]}` |
| `GET /api/compare` | `topic`, `as_of?` (ISO date or datetime, default now), `anchor=fi`, `langs?`, `section?`, `offset=0`, `limit=25` | `{topic, as_of, anchor, langs, editions:{lang:{rev_id, rev_ts}}, total_rows, rows:[{row_id, section, cells:{lang:{status:"anchor"\|"matched"\|"candidate"\|"not_found", h, page_id, text, gloss, dist, verdict, marks:[{kind:"number"\|"term", this, other}], born, died, born_rev, died_rev, time_precision, oldid_url}}}]}` |
| `GET /api/claim/{lang}/{page_id}/{h}/timeline` | | `{claim, lives:[{lang, page_id, h, text, born, died, born_rev, died_rev, died_comment, time_precision, verdict}]}` for the claim and its matched rows in other editions |
| `GET /api/dropped` | `topic?`, `lang?`, `reason?`, `min_days=365`, `offset`, `limit` | `{total, rows:[{lang, page_id, title, h, text, gloss, born, died, died_rev, died_comment, days, reason, alive_in:[{lang, h, text, verdict, oldid_url}]}], scale:{fi_lives, fi_dead, fi_dead_1y, fi_revisions}}` |
| `GET /api/sources` | `topic`, `as_of?` | `{editions:[{lang, rev_id, refs, isbn:{group:n}, domains:{domain:n}}]}` |
| `POST /api/check` | body `{text, as_of?, langs?}` | `{run_id, source, answer_model, answer_date, engine, claims:[{idx, text, per_lang:{lang:{label:"says"\|"stopped_saying"\|"contradicts"\|"not_found", evidence:[{lang, page_id, h, text, born, died, died_rev, died_comment, dist, verdict, oldid_url}]}}]}` |
| `GET /api/check/recorded` | | `{runs:[{run_id, question, answer_model, answer_date}]}` |
| `GET /api/check/{run_id}` | `as_of?` | same shape as `POST /api/check` |
| `GET /api/ask` | `q`, `as_of?`, `langs?`, `k=3` | `{q, as_of, quotes:{lang:[{text, gloss, dist, born, died, oldid_url}]}}`; no generated prose (Q13) |
| `GET /api/atlas` | `coverage?`, `offset`, `limit` | `{counts:{all, fi+sv, fi+en, fi}, topics:[{wikidata_id, titles:{fi, sv, en}, coverage, dist:{fi_sv, fi_en, sv_en}, topic_id}]}` |
| `GET /api/stats` | | `{stats:{k: v}}` from table `stat` |
| `GET /api/sql/{panel_id}` | | `{panel_id, statements:[{text, ms, rows, index}]}`, the last run of that panel |

Errors: `{"error": {"code": "...", "message": "..."}}` with HTTP 4xx or 5xx.

### 1.5 Makefile targets

Shared targets (contract, in `parallax/Makefile`): `db-up`, `db-down`, `db-reset` (drop the database, apply `contract/schema.sql`), `seed` (download `SEED` if missing, `db-reset`, load), `seed-mini`, `test-contract`, `lint`, `check-rules`, `test` (all three test sets).

Track A targets (`pipeline/targets.mk`): `fetch-smoke`, `fetch`, `parse`, `lives`, `bisect`, `embed`, `load`, `checks`, `align`, `judge`, `gloss`, `eval`, `m-lives`, `atlas`, `sources-data`, `dump`, `release`, `test-a`.

Track B targets (`api/targets.mk`): `api`, `web`, `web-build`, `test-b`, `test-web`, `e2e`, `record-checks`, `demo` (ENGINE=fake, seed loaded, API serving the built web on port 8000), `demo-check`, `record`, `deploy`.

### Done criteria for the contract

- [ ] `cd parallax && make db-up seed-mini test-contract` passes on Tim's laptop and on both track laptops.
- [ ] `make seed SEED=v1` loads; `SELECT COUNT(*) FROM claim FOR SYSTEM_TIME ALL` returns 7116.
- [ ] `uv run pytest tests/contract -q` checks: every table of section 1.1 exists with a vector index on `claim` and `article_vec`; the fake engine returns 1024-dim unit vectors twice the same; every example JSON matches its schema in `openapi.yaml`.
- [ ] The Mainila probe on seed v1 returns "staged" for en `AS OF '2008-06-01'` and "reported" for `'2012-06-01'`.
- [ ] `make check-rules` passes on the empty tracks. The CI workflow is green on `main`.
- [ ] Both track branches have merged `main`.

## 2. Track A, data and engine

Track A owns `parallax/pipeline/`, `parallax/engine/`, `parallax/eval/`, `parallax/docs/VERDA.md`, `parallax/docs/GEMINI.md`, `parallax/docs/SCALE.md`, `parallax/pipeline/targets.mk` and everything under `parallax/data/` (gitignored). It never edits `api/`, `web/`, `e2e/` or `contract/`. Its tests are in `pipeline/tests/`, `engine/tests/` and `eval/tests/`; `make test-a` runs them. Track A runs against its own local MariaDB and never waits for the app.

Background facts for the whole track:

- Demo topic: Winter War, Wikidata Q134949. Titles: fi *Talvisota* (page 1256), sv *Vinterkriget*, de *Winterkrieg*, en *Winter War*, et *Talvesõda*; the ru and uk titles mean "Soviet-Finnish war (1939 to 1940)" and are taken verbatim from the langlinks of *Talvisota* (they contain an em dash, so never type them by hand). Revisions on 14 Nov: fi 2,148, sv 781, de 1,197, en 6,720, ru 3,885, et 253, uk 660.
- History depth (Q6): fi uses every revision from the M dataset. The six other editions use yearly snapshots (the revision that was current at 00:00 UTC on 1 January of each year plus today's revision) and exact bisects for the demo claims.
- MariaDB datasets: `gh release download <tag> -R MariaDB/mariadb-wikipedia-datasets`. `m-2026-10`: 16 parquet files `versions-NN.parquet`, 19,742 fi articles, 862,076 revisions to 1 Oct 2026, columns `page_id, title, rev_id, parent_id, timestamp, user, anonymous, comment, minor, sha1, bytes, text`. Never read `user` or `anonymous`. Talvisota has 2,143 versions in `versions-01.parquet`. `s-2026-10`: `articles-{fi,sv,en}.parquet` and `vectors-bge-m3-{fi,sv,en}` with one bge-m3 vector per article; 2,919 Wikidata ids exist in all three.
- Measured on Saturday: bge-m3 through local Ollama embeds 18 sentences/s. Spike recall on 28 hand-checked cross-language pairs: R@1 0.57, R@5 0.89, R@10 0.96. At topic size exact search (`IGNORE INDEX(emb)`) took 0.7 to 3.6 ms and ANN 6 to 127 ms; ANN with `mhnsw_ef_search=80` and `LIMIT 2` once missed a row, ef 1000 never did.
- Rate tiers: 10 requests/min without a contact in the User-Agent, 200/min with one. The spike got 429 after 8 fast calls with a contact-free UA.
- Reverts: a revision is a revert when its `sha1` equals the `sha1` of an earlier revision of the same page other than its parent; it restores that earlier revision (the "revert target"). M has `sha1` for every revision and the API metadata from A2 has it too. Talvisota alone has 328 reverts, 240 of them undo anonymous edits, so with every revision (fi, and exact bisects) vandalism would otherwise show up as claims.
- Noise rule (applies only to `time_precision='exact'` lives, fixed here so A4, A5 and A12 count the same way):
  - **Noise life:** a life that lasted under 24 hours, or that was ended by a revert whose target is older than its `born_rev` (vandalism that was undone). Noise lives are not loaded into `claim` or `claim_life_fi`.
  - **Healed gap:** when a sentence dies and the same `h` is born again within 24 hours, or the revision that brings it back is a revert to a revision in which it was alive (blanking that was undone), the two lives are merged into one. Healed gaps are not deaths.
  - Raw numbers stay visible for honesty: `stat` keys `lives_raw`, `lives_noise`, `gaps_healed` per edition and for M.

### A1. Wikimedia client and cache (16:45 to 17:15, 30 min)

- **Goal:** one polite HTTP client that every fetch uses.
- **Files:** `pipeline/wapi.py`, `pipeline/tests/test_wapi.py`, `pipeline/targets.mk` (target `fetch-smoke`).
- **Inputs:** the client rules in section 0.
- **Steps:**
  1. `requests.Session` with the User-Agent from section 0; a global semaphore of 1 (setting `WIKI_PARALLEL`, capped at 3).
  2. `get(url, params)`: cache key `sha1(url + sorted params)`, file `data/raw/<key>.json.gz`; on hit return without a request. Add `maxlag=5` to Action API calls. On 429 sleep `Retry-After` (default 5 s, doubling, max 6 tries); on 5xx retry 3 times. Count calls, 429s and wait seconds in `STATS`.
  3. `fetch-smoke`: langlinks of fi *Talvisota* (`action=query&prop=langlinks|pageprops&lllimit=max&titles=Talvisota&format=json&formatversion=2`), print the six target titles and `STATS`.
- **Done check:** `uv run pytest pipeline/tests/test_wapi.py -q` passes (a fake server answers 429 with `Retry-After: 1` once, then 200; second call is a cache hit with zero requests). `make fetch-smoke` prints `sv Vinterkriget`, `de Winterkrieg`, `en Winter War`, `et Talvesõda`, the ru and uk titles starting with `Советско-финляндская война` and `Радянсько-фінська війна`. `STATS` shows `r429=0`.
- **Unblocks:** A2, A5.

### A2. Fetch Winter War (17:15 to 18:00, 45 min, fetch runs in the background)

- **Goal:** raw history for 7 editions on disk.
- **Files:** `pipeline/fetch.py`, `pipeline/topics.yaml`, `pipeline/tests/test_fetch.py`.
- **Inputs:** A1. `topics.yaml` holds `winterwar: {wikidata: Q134949, label_en: Winter War, fi_page: 1256, langs: [fi, sv, de, en, ru, et, uk]}`.
- **Steps:**
  1. Revision metadata per non-fi edition: `prop=revisions&rvprop=ids|timestamp|size|flags|sha1|comment&rvlimit=max&rvdir=newer` with continuation. Write `data/hist/winterwar/<lang>.meta.jsonl.gz`. Never request `user`.
  2. Pick snapshot revisions: for each year from the year after the first revision to 2026, the last revision before 1 January 00:00 UTC, plus the current one. Fetch their wikitext with `prop=revisions&revids=<id>|<id>...&rvprop=ids|timestamp|comment|sha1|content&rvslots=main`, 10 revids per call. Write `data/hist/winterwar/<lang>.snap.jsonl.gz` (`rev_id, ts, comment, sha1, text`).
  3. fi: read page 1256 from `versions-01.parquet` (pyarrow filter on `page_id`, columns without `user` and `anonymous`) into `data/hist/winterwar/fi.every.jsonl.gz`. Also fi metadata rows for `revision`.
  4. Print counts per edition.
- **Done check:** `make fetch TOPIC=winterwar` ends with a table where fi has 2,143 revisions with text, sv 781 and en 6,720 revisions of metadata (or more, as edits keep coming), each non-fi edition has between 19 and 26 snapshots while `r429` stays under 5. A second run makes zero requests.
- **Unblocks:** A3, A4, A5, A14.

### A3. Wikitext parser and sentence splitter (17:15 to 18:30, 75 min, in parallel with the A2 fetch)

- **Goal:** one parser for M and API wikitext, so hashes are consistent within an edition.
- **Files:** `pipeline/parse.py`, `pipeline/tests/test_parse.py`, `pipeline/tests/data/*.wiki`.
- **Inputs:** A2 output, mwparserfromhell.
- **Steps:**
  1. Split into sections by level-2 and level-3 headings; text before the first heading is `[lead]`.
  2. Remove `<ref>...</ref>` and `<ref/>`, but record per sentence whether a ref followed it (`has_ref`). Remove files, images, categories, interwiki lines (`^[a-z-]{2,12}:`), tables, comments, `{{Navbox ...}}`, `{{Sidebar ...}}` and all other templates, except a whitelist that keeps its first argument: `lang`, `nowrap`, `formatnum`, `convert` (value plus unit), `sfn` dropped. Links keep their label.
  3. The first template whose name contains `infobox`, `Infobox`, `Tietolaatikko`, `Infobox military conflict`, `Карточка` or `Конфликт` becomes `[infobox]` key/value JSON; its values also become sentences of the form `key: value` in section `[infobox]` (casualty figures live there).
  4. Splitter from the spike, kept as is: split on `(?<=[.!?])\s+` only where the next piece starts with a digit, an opening quote or bracket (`«"„(`) or a character for which `str.isupper()` is true (this covers Latin and Cyrillic capitals alike). Then glue a piece onto the previous one when the previous piece is under 25 characters or ends in a short word or abbreviation matching `\b(\d{1,2}|\w{1,3}|ym|esim|mm|ca|bzw|z\.B|u\.a|т\.е|e\.Kr|jKr|eKr)\.$`. Drop pieces under 20 characters.
  5. Output per revision: list of `{section, idx, text, h, has_ref}` with `h = claim_hash(text)`.
  6. Parse cache keyed by revision `sha1`: identical text gives an identical parse, so a revert (and any other repeat of an earlier text) reuses the cached result instead of parsing again. In memory, per page (reverts stay inside one page), so A12 needs no extra disk. Count `parsed` and `cache_hits`.
- **Done check:** `uv run pytest pipeline/tests/test_parse.py -q` with fixtures for each language: the en 2008 snapshot yields a sentence containing "the Soviets staged the Shelling of Mainila"; the current ru revision yields "по заявлению советской стороны"; Finnish "12. maaliskuuta 1940" stays in one sentence; no sentence contains `{{`, `[[`, `|` or `v t e`; the de infobox yields at least one `[infobox]` row; parsing the same `sha1` twice calls the parser once. Parsing all fi revisions of Talvisota takes under 3 minutes and prints `parsed=... cache_hits=...` (at least the 328 reverts are hits).
- **Unblocks:** A4, A12, A14.

### A4. Sentence lives (18:30 to 19:15, 45 min)

- **Goal:** turn ordered revisions into lives (rebirths included).
- **Files:** `pipeline/lives.py`, `pipeline/tests/test_lives.py`.
- **Inputs:** A3 per-revision sentence sets.
- **Steps:**
  1. Walk revisions in time order per `(lang, page_id)`. A sentence present in revision i and absent in i-1 is born at `ts(i)` with `born_rev = rev(i)`; present in i-1 and absent in i dies at `ts(i)` with `died_rev = rev(i)` and `died_comment = comment(i)`. A return after death is a new life.
  2. `time_precision = 'exact'` for fi (every revision) and `'snapshot'` for yearly editions; for snapshot lives `died_comment` stays NULL.
  3. `had_ref` is 1 if any revision of the life had a ref after the sentence, `has_ref` reflects the last revision of the life.
  4. Same `(lang, page_id, h, row_start)` twice: add 1 µs.
  5. Section rows: the same walk over `(section, sha1(section text))` gives the `section_text` lives.
  6. Exact lives only: apply the noise rule from the background facts (heal gaps first, then drop noise lives). Revert detection uses the `sha1` of every revision in time order.
  7. Write `data/lives/winterwar-<lang>.jsonl.gz` and print per edition: lives, alive, dead, distinct texts, and for exact editions also `lives_raw`, `lives_noise`, `gaps_healed`.
- **Done check:** `uv run pytest pipeline/tests/test_lives.py -q` covers a 4-revision toy history (born, died, reborn, still alive gives 2 lives for one `h`, with gaps of more than 24 hours), plus noise cases: a sentence added and reverted after 10 minutes gives no life; a section blanked and reverted after 5 minutes gives one unbroken life; a sentence removed and re-added 3 days later by a normal edit gives 2 lives. `make lives TOPIC=winterwar` prints counts; en has a dead life containing "staged the Shelling of Mainila" that ends in 2010 (snapshot bound; A5 makes it exact); fi shows `lives_noise > 0`.
- **Unblocks:** A5, A6, A7.

### A5. Exact bisect for demo claims (19:15 to 19:45, 30 min)

- **Goal:** exact edit, date and comment for every claim the demo shows changing.
- **Files:** `pipeline/bisect.py`, `pipeline/demo_claims.yaml`, `pipeline/tests/test_bisect.py`.
- **Inputs:** A2 metadata, A4 lives.
- **Steps:**
  1. `demo_claims.yaml` lists `(lang, regex)` pairs: en `staged the Shelling of Mainila`; ru `инсценированный советской стороной`; ru `предположительно инсценированный`; sv `rysk provokation`; de `Vorwand`; de `inszenierte`; fi `tekaistuihin`. More can be added.
  2. For each pair, find the first and last snapshot that match, then binary search over the metadata revision list between them, fetching single revisions with `revids=<id>&rvprop=content` (about 12 calls each).
  3. Replace the life's snapshot bounds by exact `ts`, `born_rev`, `died_rev` and `died_comment`; set `time_precision='exact'`. If the first revision without the claim is a revert or is undone within 24 hours, keep bisecting past it (noise rule), so the demo never shows a vandal edit as the moment a claim changed.
- **Done check:** `make bisect TOPIC=winterwar` prints en `first_without=309285088 2009-08-21T18:00:56Z` with a comment containing "rewrote the mainila incident part" and ru `first_without=64106894 2014-07-09T10:22:55Z`. Unit test runs the binary search on a fake revision list.
- **Unblocks:** the Time scene of the demo.

### A6. Embeddings with Verda or local fallback (18:00 to 20:15, timeboxed)

- **Goal:** every distinct sentence text embedded once with bge-m3 (Q8).
- **Files:** `engine/embed.py`, `engine/embed_server.py`, `engine/real.py` (embed part), `pipeline/embed.py`, `engine/tests/test_embed.py`.
- **Inputs:** A4 distinct texts.
- **Steps:**
  1. `engine/embed.py` with three backends chosen by `EMBED_BACKEND`: `ollama` (POST `EMBED_URL/api/embed`, model `bge-m3`, batches of 32), `st` (sentence-transformers `BAAI/bge-m3`, fp16, batch 128, for a GPU) and `remote` (POST `EMBED_URL/embed` to our own server). Always L2-normalise.
  2. `engine/embed_server.py`: FastAPI with `POST /embed {texts}` returning vectors, using backend `st`. It runs on the Verda GPU instance and listens on 127.0.0.1 only; the laptop reaches it through `ssh -L 9100:127.0.0.1:9100`.
  3. Verda (human of Track A, started at 17:00 in parallel): GPU instance (an A100 or H100 is plenty), install `uv`, clone the repo, `uv sync --extra gpu`, `uv run uvicorn engine.embed_server:app --port 9100`. Record instance type, setup minutes, sentences/s and cost in `docs/VERDA.md` as you go. **Hard stop: if the first vector does not come back from Verda by 19:30, switch to `ollama` and drop the Verda claim.**
  4. `pipeline/embed.py`: distinct texts not yet in `data/emb/` go to the backend; store `data/emb/<h>.npy` shards (or one `npz` per 10k); print texts/s.
- **Done check:** `uv run pytest engine/tests/test_embed.py -q` (vectors have 1024 dims and norm 1 ± 1e-3; a cached text causes no call). `make embed TOPIC=winterwar` prints `distinct=... embedded=... rate=...`. Cosine distance between the en and de Mainila sentences is under 0.35.
- **Unblocks:** A7, A12 vectors.

### A7. Load, checks and seed v2 (20:15 to 21:00, 45 min)

- **Goal:** the full Winter War in MariaDB and a dump for Track B at M1.
- **Files:** `pipeline/load.py`, `pipeline/checks.sql`, `pipeline/checks_expected.txt`, `pipeline/tests/test_load.py`.
- **Inputs:** A4, A5, A6, `contract/schema.sql`.
- **Steps:**
  1. `make db-reset`, then insert `topic`, `page`, `revision` (all metadata rows, `snapshot=1` for parsed ones), `section_text`, `claim`. Session: `SET time_zone='+00:00'; SET system_versioning_insert_history=1`. History rows first with explicit `row_start, row_end`, then current rows with `row_start` only. Batches are cut by size, not by row count: at most 500 rows and at most 4 MB of SQL per statement, because long `section_text` rows would otherwise exceed the default `max_allowed_packet` (16 MB). One transaction per edition. Record load seconds per table for A13b. The loader is idempotent (reset and reload).
  2. `term` from `pipeline/terms.yaml` (the Mainila verbs per language: fi lavasti, tekaistu; de inszenierte, Vorwand, angeblich; sv provokation, bevisas; en staged, reported, false flag; ru инсценир, провокац, по заявлению советской стороны; et provokatsioon; uk провокац, інсценув) and `term_hit` from regex over claim lives with the same periods.
  3. `checks.sql`: row counts per edition (current and history), the Mainila probe (en `AS OF '2008-06-01'` nearest to the en Mainila vector is the "staged" sentence, `AS OF '2012-06-01'` the "reported" one), `EXPLAIN` shows `key=emb`. `make checks` diffs the output against `checks_expected.txt`.
  4. `make dump`: `mariadb-dump --dump-history --single-transaction parallax | gzip > data/seed.sql.gz`; `make release SEED=v2`.
- **Done check:** `make load checks` ends with `checks OK`; `make release SEED=v2` prints the release URL. Load of the Winter War takes under 5 minutes.
- **Unblocks:** M1, A8, B on real data.

### A8. Alignment cache (21:00 to 21:30, 30 min)

- **Goal:** top 5 candidates per claim and edition for the anchor dates the UI uses.
- **Files:** `pipeline/align.py`, `pipeline/align.sql`, `pipeline/tests/test_align.py`.
- **Inputs:** A7.
- **Steps:**
  1. Anchor dates: 2006-01-01, 2010-01-01, 2014-01-01, 2018-01-01, 2022-01-01 and today.
  2. For each date, each source claim alive `AS OF` that date and each other edition, exact top 5 in one statement: `SELECT h, page_id, VEC_DISTANCE_COSINE(emb, ?) d FROM claim FOR SYSTEM_TIME AS OF ? IGNORE INDEX(emb) WHERE topic_id=? AND lang=? ORDER BY d LIMIT 5`. Insert into `align` with `method='exact'`.
  3. Time 100 of them also with the index (`method='ann'`, ef 1000) and write the comparison to `stat` key `align_ann_vs_exact`.
- **Done check:** `make align TOPIC=winterwar` prints rows per date; for today the en Mainila sentence has the de "inszenierte" sentence at rank 1 or 2. Test checks there are no duplicates and ranks run 1..5.
- **Unblocks:** A9, B's Compare at anchor dates.

### A9. Gemini judge, splitter and gloss (21:30 to 23:00, 90 min)

- **Goal:** the real engine (Q10). The team chose Gemini over Nemotron on Saturday afternoon as the safer bet.
- **Files:** `engine/real.py` (class `GeminiEngine`, which `contract.engine.get_engine()` loads for `ENGINE=real`), `engine/gemini.py`, `engine/prompts/judge-v1.txt`, `split-v1.txt`, `gloss-v1.txt`, `pipeline/judge.py`, `pipeline/gloss.py`, `engine/tests/test_real_parse.py`.
- **Inputs:** A8, `GEMINI_API_KEY` in `.env`. There is one key; Tim sends it to each human by DM. It is never committed, logged or pasted anywhere else.
- **Steps:**
  1. `engine/gemini.py`: the `openai` client (already a dependency, so no new package) on Gemini's OpenAI-compatible endpoint, `base_url=https://generativelanguage.googleapis.com/v1beta/openai/`, `api_key=GEMINI_API_KEY`, model `gemini-3.8-flash`, temperature 0, `response_format={"type": "json_object"}`, thinking kept low with `reasoning_effort="minimal"` (if the endpoint rejects that value, use `"low"` and note it in GEMINI.md). Rate limits: all of us share one key and so one quota, so a token bucket of 60 requests/min (constant `RPM` at the top of the file; set it to the limit AI Studio shows for the key) and at most 4 requests in flight. Retries: on 429 and 5xx wait `Retry-After` if present, else 2 s doubling up to 60 s, at most 5 attempts; after that the pair stays unjudged and the UI shows "candidate, not judged". Timeout 60 s per call, one extra retry on unparseable JSON. Log calls, 429s and retries, never the key.
  2. Judge prompt: one claim plus up to 5 candidates in other languages, numbered. Answer only JSON `{"results":[{"i":1,"label":"same|partial|contradicts|different","numbers":[["a","b"]],"terms":[["a","b"]]}]}`. Definitions in the prompt: same = states the same fact; partial = overlaps, one says more; contradicts = same subject, incompatible fact or number; different = another fact. Neutral: no judgement on which edition is right.
  3. Split prompt: an AI answer into claims of at most about 20 words, one fact each, in the answer's language, JSON list. Only for pasted answers (Q7).
  4. Gloss prompt: up to 20 sentences into English, JSON list in the same order.
  5. `pipeline/judge.py`: every `align` pair for today plus the anchor dates of the demo rows, skipping pairs already in `verdict` for this `prompt_version`. `pipeline/gloss.py`: every non-en sentence that is current or appears in `demo_claims.yaml`.
- **Done check:** `uv run pytest engine/tests/test_real_parse.py -q` (parsing of recorded raw answers, including one with prose around the JSON). `make judge TOPIC=winterwar` prints `pairs judged, calls, 429s, minutes`; the en Mainila "reported" vs de "inszenierte" pair has label `partial` or `contradicts` and a non-empty `terms`. `make gloss` fills `gloss` for every current non-en claim of the topic.
- **Unblocks:** A10, B's real verdicts and live Check, M2.

### A10. Gold set and evaluation (23:00 to 00:15, 75 min, 20 min of it human labelling)

- **Goal:** a measured agreement number for the judge and recall numbers for alignment.
- **Files:** `eval/gold.py`, `eval/label.py`, `eval/score.py`, `eval/gold.jsonl` (committed, no user data), `eval/report.json`, `eval/tests/test_score.py`.
- **Inputs:** A8, A9.
- **Steps:**
  1. Candidate pairs: the six spike anchors in en with their counterparts in fi, sv, de, ru and et, found by regex: start of the war (`^It began with a Soviet invasion of Finland on 30 November 1939`), League of Nations (`^The League of Nations deemed the attack illegal`), peace (`^Hostilities ceased in March 1940`), Mainila (`^On 26 November 1939, an incident was reported`), puppet government (`^On 1 December 1939, the Soviet Union formed a puppet government`), Raate road (`^The Battle of Raate Road`). Add uk and 12 random aligned pairs per label for 40 to 60 pairs.
  2. `eval/label.py`: a terminal loop that shows both sentences with glosses and asks the human for `same/partial/contradicts/different`. Store in `gold_pair` and `eval/gold.jsonl`.
  3. `eval/score.py`: judge accuracy and Cohen's kappa overall and per language; alignment R@1, R@5, R@10 against the gold `same` pairs; write `eval/report.json` and `stat` key `judge_eval`.
  4. Write `judge-v2.txt` with the fixes the misses suggest (typical: partial vs same on sentences that pack two facts), rerun on the gold set only, keep the better version as default. Both numbers go into GEMINI.md.
  5. Optional, only if time allows before M2: run the same gold set through `nvidia/nemotron-3.5-super-vl-120b-a12b` as a second judge (your human creates an NVIDIA key at build.nvidia.com then) and add its accuracy and kappa next to Gemini's in `eval/report.json` and GEMINI.md. The app keeps Gemini as its only judge; skip this step without asking if A11 is due.
- **Done check:** `make eval` prints `pairs=N accuracy=... kappa=...` per prompt version and per language. `uv run pytest eval/tests -q` checks the scorer on a toy set.
- **Unblocks:** Gemini form text, the agreement number in the demo.

### A11. Seed v3 for M2 (00:15 to 00:45, 30 min)

- **Goal:** everything B needs for the real demo in one dump.
- **Files:** `pipeline/targets.mk`.
- **Steps:** run `make checks`, write `stat` keys (`revisions_total`, `lives_total`, `lives_raw`, `lives_noise`, `gaps_healed`, `distinct_texts`, `vectors`, `embed_rate`, `judge_calls`), `make dump release SEED=v3`.
- **Done check:** `make seed SEED=v3` on a clean database followed by `make checks` prints `checks OK`.
- **Unblocks:** M2.

### A12. Finnish lives for all of M (start 21:30 in the background, 90 min of CPU; 30 min of agent work)

- **Goal:** the scale layer: every sentence life in 862,076 Finnish revisions.
- **Files:** `pipeline/m_lives.py`, `pipeline/tests/test_m_lives.py`.
- **Inputs:** A3, A4 and the 16 M parquet files in `data/m/`.
- **Steps:**
  1. One file at a time, group by `page_id`, sort by `timestamp`, parse with A3 (with its `sha1` parse cache), lives with A4 (`time_precision='exact'`, noise rule applied). Read only the columns `page_id, title, rev_id, parent_id, timestamp, comment, minor, sha1, bytes, text`. Use a process pool of `cpu_count()-1`. Print a progress line per file with revisions/s and the cache hit rate, so the CPU time is known early: if the first file projects more than 120 minutes in total, tell your human and restrict A12 to the articles in the S atlas (A13) plus every article with at least one `unsourced` or `error` death.
  2. `reason` from `died_comment`: `unsourced` for `lähteetön|lähde puuttuu|ei lähdettä|lähteitä`, `error` for `virhe|väärä|korjaus`, `speculation` for `spekul|huhu|arvailu`, `other` for any other non-empty comment, `none` for empty.
  3. Load into `claim_life_fi` (history rows with insert_history, batches cut by size as in A7). Print lives, alive, dead, dead after at least 365 days, per reason, and `lives_raw`, `lives_noise`, `gaps_healed`, `parsed`, `cache_hits`, CPU minutes.
  4. Embedding subset for `claim`: lives that are alive or lived at least 365 days. With Verda up, embed all of them; without, the 100 articles with the most `unsourced` or `error` deaths. Load into `claim` with `topic_id=NULL`.
  5. Contested claims (edit wars at the level of a single sentence), pure SVT, no new table: `pipeline/contested.sql` counts lives per sentence over the whole history, `SELECT page_id, h, COUNT(*) lives FROM claim_life_fi FOR SYSTEM_TIME ALL GROUP BY page_id, h HAVING lives >= 3`. Because gaps were healed and noise dropped first, a count of 3 or more means people removed and restored the sentence repeatedly, not vandalism. Write `stat` key `contested_claims` (total, per-article top 20 with title and the sentence text, query milliseconds) and print the Talvisota ones. Target `make contested`.
- **Done check:** `make m-lives` prints totals in the order of the Friday spike (about 1 million raw lives; the parser changed, so report the new numbers and do not reuse the old ones). `SELECT COUNT(*) FROM claim_life_fi FOR SYSTEM_TIME ALL` matches the printed total after noise. The Talvisota rows in `claim_life_fi` equal the fi lives from A4. `make contested` prints the total and a top 20 in which every entry has at least 3 lives. `uv run pytest pipeline/tests/test_m_lives.py -q` covers the parquet reader on a 3-page toy file (no `user` column read) and the contested query on toy rows.
- **Unblocks:** Dropped view scale line, Check across all of fi, the contested line in SCALE.md and the submission text.

### A13. S atlas (00:45 to 01:30, 45 min)

- **Goal:** breadth across 2,919 tri-lingual topics.
- **Files:** `pipeline/atlas.py`, `pipeline/tests/test_atlas.py`.
- **Steps:** load `article_vec` from the S vector files; fill `atlas_topic` with titles, coverage and the three pairwise distances computed in SQL (`VEC_DISTANCE_COSINE(a.emb, b.emb)` joined on `wikidata_id`); set `topic_id='winterwar'` for Q134949.
- **Done check:** `make atlas` prints `all=2919`; `SELECT coverage, COUNT(*) FROM atlas_topic GROUP BY coverage` matches. Writes `stat` key `atlas` (topics per coverage, SQL milliseconds for the distance query, the 10 topics with the largest fi–sv and fi–en distance as "where to look next").
- **Unblocks:** B10, A13b.
- **Cut note (proposal for Tim):** A13 is the cheapest task that runs entirely on a provided dataset (S). If Atlas is cut (section 6, item 1), cut only the UI (B10) and keep A13: its numbers still go into the scale line and SCALE.md.

### A13b. Scale bench (after A13, 30 min, uses the slack from the early contract)

- **Goal:** measured numbers for the "Implementation: scalability on the provided datasets" criterion (20 %), from one command.
- **Files:** `pipeline/bench.py`, `pipeline/tests/test_bench.py`, `docs/SCALE.md`, target `bench` in `pipeline/targets.mk`.
- **Inputs:** A7, A12, A13 loaded in the local database.
- **Steps:**
  1. Sizes: rows (current and `FOR SYSTEM_TIME ALL`) and `data_length + index_length` from `information_schema.tables` for `claim`, `claim_life_fi`, `article_vec`, `section_text`, `revision`; load seconds recorded by A7 and A12; parse rate and cache hit rate from A12.
  2. `AS OF` latency: 50 random `(page_id, date)` pairs, p50 and p95, once on the Winter War (`claim`) and once across all of M (`claim_life_fi`); `EXPLAIN` must show the `(page_id, row_start)` key, otherwise the bench fails.
  3. Vector search at M size: 100 random `claim` vectors, exact (`IGNORE INDEX(emb)`) vs ANN with `mhnsw_ef_search` 20, 80 and 1000: recall@10 against exact and p50/p95 milliseconds, with the vector search in a subquery and the join after it.
  4. The combined statement of the demo (`AS OF` plus `VEC_DISTANCE_COSINE`) on the Winter War: p50/p95 and rows.
  5. Write everything to `stat` key `bench` and render `docs/SCALE.md` from it: one table per dataset (M, S, Winter War from the API, L if A17 ran), the noise numbers (`lives_raw`, `lives_noise`, `gaps_healed`), the contested claims count, and one paragraph on why sentences are the chunks (the "chunking" the organisers list as to do: one vector per sentence life finds a fact, not just a topic, and one vector per life instead of per revision keeps the vector count at distinct sentences).
- **Done check:** `make bench` prints the tables and `bench OK`; every number in `docs/SCALE.md` is in `stat`. `uv run pytest pipeline/tests/test_bench.py -q` checks the percentile and recall helpers on toy data.
- **Unblocks:** the scale line in Under the hood, the "Implementation" paragraph of the submission, A16.

### A14. Source statistics (01:30 to 02:00, 30 min)

- **Goal:** data for the Sources view through time.
- **Files:** `pipeline/sources.py`, `pipeline/tests/test_sources.py`.
- **Steps:** for each snapshot (fi: one per year from M) count `<ref` tags, ISBN groups (map: 951 and 952 FI, 91 SE, 3 DE, 5 RU/USSR, 0 and 1 EN, 9985 and 9949 EE, 966 and 617 UA, 985 BY, 82 NO, 87 DK, 90 and 94 NL, 2 and 10 FR, 83 PL; 978/979 prefixes stripped) and URL domains; load `ref_stat` as lives.
- **Done check:** `make sources-data` prints the current fi row with at least 90 % FI among its ISBNs (Saturday's HTML count was 78 of 82) and en with the most refs.
- **Unblocks:** B8.

### A15. Recorded answers (02:00 to 02:30, 30 min)

- **Goal:** AI answers for the Check view that do not depend on the network on stage.
- **Files:** `pipeline/record_answers.py`, `pipeline/answers.yaml`.
- **Steps:** 5 questions about the Winter War and Mainila (who fired the Mainila shots, how many Finnish soldiers died, how much territory Finland ceded, when the war ended, what the Terijoki government was). Ask each to `gemini-3.8-flash` and to `gemma-4-31b-it` through the same Gemini endpoint and key, temperature 0 (if the key does not list the Gemma model, take only Gemini and store 5 answers). Store question, model, date and answer in `data/answers.json` and hand the file to B (copy into `contract/fixtures/answers.json` through a contract commit by Tim).
- **Done check:** 10 answers (or 5 without Gemma) stored with model id and date.
- **Unblocks:** B6 recorded runs.

### A16. Side quest docs and final data (02:30 to 04:30)

- **Goal:** `docs/GEMINI.md`, `docs/VERDA.md` (section 5), a final `make bench` run for `docs/SCALE.md` and the final dump.
- **Steps:** numbers from `stat` and `eval/report.json` only; rerun `make bench` on the final data; `make dump release SEED=final` at 04:30.
- **Done check:** all three docs exist, every number in them is in `stat` or `eval/report.json`; `make seed SEED=final checks` prints `checks OK`.
- **Unblocks:** M3, the submission form.

### A17. Dataset L at scale (optional, only while the Verda GPU is up, background)

- **Goal:** turn L (568,416 current fi articles) from a promise in VERDA.md into a measured number.
- **Files:** `pipeline/l_scale.py`, `pipeline/tests/test_l_scale.py`.
- **Inputs:** `l-2026-10` from the MariaDB datasets release, `engine/embed.py` (A6).
- **Steps:**
  1. L text is clean Markdown, so the wikitext parser is not needed: `split_sentences` and `claim_hash` from the contract over every article, one parquet file at a time. Print articles, sentences, distinct hashes, sentences/s.
  2. With Verda up: embed the distinct sentences of a 10,000-article sample with backend `remote`, measure sentences/s and project hours and credits for all of L. No load into `claim` (schema and demo stay as they are).
  3. Write `stat` key `l_scale`; A13b adds an L table to SCALE.md and VERDA.md gets the measured projection.
- **Done check:** `make l-scale` prints the totals and, with Verda, the measured rate and the projection. Unit test splits a toy Markdown article.
- **Cut:** first thing to drop, without asking, if anything in A1 to A16 is late or Verda is down.

## 3. Track B, app

Track B owns `parallax/api/`, `parallax/web/`, `parallax/e2e/`, `parallax/deploy/`, `parallax/docs/DEMO.md` and `parallax/api/targets.mk`. It never edits `pipeline/`, `engine/`, `eval/` or `contract/`. It imports the engine only through `contract.engine.get_engine()`. Until M1 it runs on seed v1 with `ENGINE=fake`. Tests: `api/tests/` (pytest against MariaDB with `seed-mini`), `web/src/**/*.test.ts` (vitest), `e2e/` (Playwright). All SQL for the views is in `api/queries/*.sql`, one file per panel, so "Under the hood" can show the text.

Background facts for the whole track:

- Stack (Q2, Q3): Python 3.12, FastAPI, pymysql; Vue 3.5.44 with Vite; Codex 2.7.0.
- Codex stays out of the repo and the bundle. `web/index.html` has an import map: `"vue": "https://cdn.jsdelivr.net/npm/vue@3.5.44/dist/vue.esm-browser.prod.js"`, `"@wikimedia/codex": "https://cdn.jsdelivr.net/npm/@wikimedia/codex@2.7.0/dist/codex.js"` (its only import is `vue`). Vite marks both as `external` in `build.rollupOptions`. Stylesheets from jsDelivr: `@wikimedia/codex@2.7.0/dist/codex.style-bidi.css`, `@wikimedia/codex-design-tokens@2.7.0/dist/theme-wikimedia-ui.css` and `theme-wikimedia-ui-mode-dark.css` with `media="(prefers-color-scheme: dark)"`. The npm packages are dev dependencies for types and tests only, pinned exactly. Icons from `@wikimedia/codex-icons@2.7.0` (MIT) may be bundled, never a `cdxIconLogo*`.
- Useful Codex parts: `CdxTabs` for the views, `CdxTable` for Compare, `CdxCard`, `CdxMessage` for notices, `CdxInfoChip` for labels, `CdxLookup` for topics, `CdxSelect` and a range input for the date, `CdxProgressBar`. Tokens: `--color-base`, `--font-family-system-sans`, `--font-family-serif`, spacing and border tokens.
- Each edition's cell carries `lang` and `dir` attributes. Every quote links to `https://<lang>.wikipedia.org/?oldid=<rev>`. Buttons that open Wikipedia say "Open on <lang>.wikipedia".
- DB session for every request: `SET time_zone='+00:00'`, `SET mhnsw_ef_search=1000`. Prepared `TIMESTAMP` parameters need a full datetime string (`'2012-06-01 00:00:00'`), not a bare date.

### B1. API skeleton (16:45 to 17:30, 45 min)

- **Goal:** a running API on seed data with SQL timing on every response.
- **Files:** `api/main.py`, `api/db.py`, `api/sqllog.py`, `api/routes/health.py`, `api/routes/topics.py`, `api/queries/topics.sql`, `api/tests/conftest.py`, `api/tests/test_health.py`, `api/targets.mk`.
- **Inputs:** contract, `seed-mini.sql`.
- **Steps:**
  1. `db.py`: a small connection pool from `.env`, session settings above.
  2. `sqllog.py`: a per-request context that times every statement and appends `{text, ms, rows, index}` (index from `EXPLAIN` when the query has `VEC_DISTANCE`); a FastAPI middleware puts it into the JSON as `sql`.
  3. `GET /api/health`, `GET /api/topics`, `GET /api/stats`, `GET /api/sql/{panel_id}` (keeps the last statements per panel in memory).
  4. `api/tests/conftest.py` loads `seed-mini.sql` into a test database `parallax_test`.
- **Done check:** `make test-b` passes; `make api` then `curl -s localhost:8000/api/health` returns `"db": "ok", "engine": "fake"`; `/api/topics` returns `winterwar` with 6 editions on seed v1.
- **Unblocks:** B3 to B10.

### B2. Web skeleton and layout (17:30 to 18:30, 60 min)

- **Goal:** the shell around every view, with our own look.
- **Files:** `web/package.json`, `web/package-lock.json`, `web/vite.config.ts`, `web/index.html`, `web/src/main.ts`, `web/src/App.vue`, `web/src/api.ts`, `web/src/components/Footer.vue`, `web/src/components/Wordmark.vue`, `web/src/App.test.ts`.
- **Steps:**
  1. Vite + Vue with the import map and externals from the background facts. `api.ts` wraps fetch with types generated from `contract/openapi.yaml` (`openapi-typescript`).
  2. Layout: a slim top bar with the text wordmark "Parallax" in the serif token and the topic picker; tabs Compare, Time, Dropped, Check, Sources, Ask, Atlas, Under the hood; a global date control that every view reads from the URL (`?as_of=`); the footer text from section 0 on every page. Wide grid, one column per edition; nothing that resembles an article page.
  3. Dark mode through the token stylesheet. Empty states for "no data yet".
- **Done check:** `make test-web` (vitest renders App, the footer text is present, no element has a class containing `vector-` or `mw-`). `make web` serves the shell; `make check-rules` passes; `make web-build` produces a `dist/` without Codex code: `grep -c 'cdx-button--action' web/dist/assets/*.js` prints 0 (Codex's own class strings are not bundled) and `dist/index.html` contains the import map.
- **Unblocks:** all views.

### B3. Compare (18:30 to 20:30, 120 min)

- **Goal:** the opening scene of the demo.
- **Files:** `api/routes/compare.py`, `api/queries/compare_anchor.sql`, `api/queries/compare_match.sql`, `api/marks.py`, `api/tests/test_compare.py`, `web/src/views/CompareView.vue`, `web/src/components/ClaimCell.vue`, `web/src/views/CompareView.test.ts`.
- **Steps:**
  1. Anchor rows: claims of the anchor edition alive `AS OF as_of`, `[infobox]` and `[lead]` first, then by section order, paged.
  2. Per row and other edition: if `as_of` equals an `align` date, read `align`; else one statement per row with `FOR SYSTEM_TIME AS OF` and `VEC_DISTANCE_COSINE` on `claim` (exact per topic, `IGNORE INDEX(emb)`), top 5. Then pick the best candidate whose `verdict` is `same` or `partial`; with no verdict take rank 1 as `status: candidate`; with only `different` verdicts or no row `status: not_found`.
  3. `marks.py`: numbers extracted from both texts (digits with spaces, commas or dots as group separators, percentages); a differing number becomes a `number` mark; verdict `terms` become `term` marks.
  4. UI: one row per anchor claim, one column per edition. A cell shows the original sentence, the gloss under it in smaller type with the label "machine translation", the verdict chip, marks in colour, the oldid link. `not_found` cells say "not found in <lang>". A click on a cell opens the timeline drawer (B4).
- **Done check:** `uv run pytest api/tests/test_compare.py -q` on seed-mini: the Mainila row has cells in all 6 editions, Finnish dead shows a `number` mark between fi and sv. `curl 'localhost:8000/api/compare?topic=winterwar&anchor=fi&limit=25'` returns under 1 s on seed v1. The vitest renders `contract/examples/compare.json` with "not found in" for a null cell and no forbidden word.
- **Unblocks:** B4, demo scene 0:08.

### B4. Time (20:30 to 21:30, 60 min)

- **Goal:** the slider scene.
- **Files:** `api/routes/timeline.py`, `api/queries/timeline.sql`, `api/tests/test_timeline.py`, `web/src/components/DateSlider.vue`, `web/src/components/LifeBars.vue`, `web/src/views/TimeView.vue`.
- **Steps:**
  1. Slider over years from 2003 to today, snapping to 1 January plus the exact dates of demo edits from the data (lives with `time_precision='exact'` in demo rows). Dragging updates `as_of` in the URL and refetches Compare (debounced 150 ms).
  2. `GET /api/claim/{lang}/{page_id}/{h}/timeline`: the claim's lives and the lives of its matched rows in other editions (`FOR SYSTEM_TIME ALL`).
  3. LifeBars: one bar per edition from born to died, edit comment and oldid on hover; snapshot-precision ends drawn hatched with the note "known to the year".
- **Done check:** pytest: the en Mainila timeline on seed v2 (after M1) returns a life ending 2009-08-21 with died_rev 309285088. On seed v1 the same life ends at the 2010 snapshot with `time_precision: snapshot`. Playwright step: moving the slider from 2008 to 2012 changes the en cell from "staged" to "reported".
- **Unblocks:** demo scene 0:30.

### B5. Dropped here, alive there (21:30 to 22:30, 60 min)

- **Goal:** the Dropped here, alive there view across editions and the fi scale.
- **Files:** `api/routes/dropped.py`, `api/queries/dropped_topic.sql`, `api/queries/dropped_fi.sql`, `api/tests/test_dropped.py`, `web/src/views/DroppedView.vue`.
- **Steps:**
  1. Topic mode: rows of `claim FOR SYSTEM_TIME ALL` with `row_end < NOW()`, no current row with the same `(lang, page_id, h)`, lived at least `min_days`; for each, current rows of other editions with verdict `same` or `partial` (through `align` today or a live AS OF vector query). Sort by days alive.
  2. fi mode: `claim_life_fi` dead lives, filter by `reason`, with `scale` counts from `stat`.
  3. UI: card per dropped claim with the sentence, dates, edit comment, "Open the last revision that had it" (`?oldid=<the revision before died_rev>`) and chips for the editions that still state it.
- **Done check:** pytest on seed v2: the ru "инсценированный советской стороной" life appears with `died_rev=64106894` and `alive_in` containing de. `make test-b` green.
- **Unblocks:** demo scene 0:55.

### B6. Check an answer (22:30 to 00:30, 120 min)

- **Goal:** paste or pick an AI answer, see per-edition labels.
- **Files:** `api/routes/check.py`, `api/checker.py`, `api/queries/check_nearest.sql`, `api/tests/test_check.py`, `web/src/views/CheckView.vue`, `web/src/components/ClaimLabels.vue`.
- **Steps:**
  1. `checker.py`: `split_claims` then `embed`; per claim one statement over `claim FOR SYSTEM_TIME ALL` ordered by `VEC_DISTANCE_COSINE`, `LIMIT 30` (ANN, ef 1000), grouped per edition in Python to the top 5 each; `judge` per edition; labels: `says` if a current row is `same`/`partial`, else `stopped_saying` if a dead row is `same`/`partial` (show the latest death), `contradicts` if any row contradicts, else `not_found`. With `as_of`, "current" means alive `AS OF as_of`.
  2. Store `check_run` and `check_claim`; `GET /api/check/{run_id}` replays without calling the engine.
  3. Recorded runs: after M2, `make record-checks` runs each answer from `contract/fixtures/answers.json` once with `ENGINE=real` and stores it with `source='recorded'`. It runs locally for testing and once more on the demo instance right after the final seed is loaded (B12).
  4. UI: textarea plus a picker of recorded answers, a note "recorded answer from <model>, <date>" or "live, judged by <model_id>", one row per claim with one chip per edition, evidence expandable with oldid links.
- **Done check:** pytest with `ENGINE=fake` on seed-mini: the fixture answer about Mainila yields at least one `says` and one `stopped_saying`; a replay returns the same JSON. With `ENGINE=real` (manual, after M2): a 5-claim answer takes under 15 s.
- **Unblocks:** demo scene 1:15.

### B7. Under the hood (00:30 to 01:00, 30 min)

- **Goal:** the SQL panel and the scale line.
- **Files:** `web/src/views/HoodView.vue`, `web/src/components/SqlPanel.vue`.
- **Steps:** a collapsible panel under every view showing the `sql` array of its last response (statement, ms, rows, index used). The Hood view shows the canonical statement of the demo with its live timing plus the `stat` numbers: revisions, lives, distinct texts, vectors, embed rate, judge agreement.
- **Done check:** vitest renders the panel from `contract/examples/compare.json`; Playwright opens Hood and finds `FOR SYSTEM_TIME AS OF` and `VEC_DISTANCE_COSINE` in one statement.
- **Unblocks:** demo scene 1:35.

### B8. Sources (01:00 to 01:45, 45 min)

- **Files:** `api/routes/sources.py`, `api/queries/sources.sql`, `api/tests/test_sources.py`, `web/src/views/SourcesView.vue`.
- **Steps:** `ref_stat FOR SYSTEM_TIME AS OF`; one stacked bar per edition by ISBN group plus the top domains; caption words "cites mostly". No verdict.
- **Done check:** pytest on seed v3 returns 7 editions for today; Playwright sees 7 bars.

### B9. Ask (01:45 to 02:30, 45 min)

- **Files:** `api/routes/ask.py`, `api/queries/ask.sql`, `api/tests/test_ask.py`, `web/src/views/AskView.vue`.
- **Steps:** embed the question; per edition `AS OF as_of` top `k` by `VEC_DISTANCE_COSINE`; return quotes only. UI: one column per edition with the quotes, glosses and oldid links. A note says the page quotes Wikipedia and writes nothing of its own.
- **Done check:** pytest with fake engine returns quotes for every edition in seed-mini; no field with free text beyond quotes and glosses.

### B10. Atlas (02:30 to 03:15, 45 min, first to cut)

- **Files:** `api/routes/atlas.py`, `api/queries/atlas.sql`, `web/src/views/AtlasView.vue`.
- **Steps:** counts per coverage; a sortable table of topics with the three distances; rows with `topic_id` link to Compare.
- **Done check:** pytest on seed v3 returns `counts.all=2919`.

### B11. Demo check end to end (03:15 to 04:00, 45 min)

- **Goal:** one command that walks the demo script and fails loudly.
- **Files:** `e2e/demo.spec.ts`, `e2e/playwright.config.ts`, `docs/DEMO.md`.
- **Steps:** Playwright follows the table in section 0 step by step and asserts the visible facts: the Mainila row in 7 columns, "differs" marks on the Finnish dead, the en cell flipping at 2009 with the comment text, the ru dropped card with 2014-07-09, a recorded Check run with a `stopped_saying` chip, the SQL statement in Hood, the footer text. `make demo-check` runs it against `make demo`; `BASE_URL=https://... make demo-check` against the deployed instance.
- **Done check:** `make demo-check` prints `passed` for every step twice in a row from `make seed SEED=v3`.

### B12. Deploy on a Verda CPU instance (04:00 to 05:00, 60 min)

- **Goal:** the public demo link (Q12) with one shared MariaDB (Q4).
- **Files:** `deploy/docker-compose.prod.yml`, `deploy/Caddyfile`, `deploy/README.md`, `api/targets.mk` target `deploy`.
- **Steps:** Track A's human creates the CPU instance (4 vCPU, 16 GB) in the same Verda account and adds Track B's SSH key. Compose: `db` (mariadb:12.3.3, same `my.cnf`), `api` (uvicorn serving `web/dist` as static files), `caddy` with HTTPS on `<ip>.sslip.io`. `.env` is copied over SSH and never committed. Load `seed-final` (or v3 until then). The Gemini key on the server is only for live Check; recorded runs need no key.
- **Done check:** `BASE_URL=https://<ip>.sslip.io make demo-check` passes; `curl -s https://<ip>.sslip.io/api/health` shows the seed name.
- **Unblocks:** M3, the demo link in the submission.

### B13. Recording helper (05:00 to 05:30, 30 min)

- **Files:** `e2e/record.spec.ts`.
- **Steps:** the demo path with pauses that fit the 2:00 table and Playwright video at 1920×1080, `make record` writes `e2e/results/demo.webm` for Tim.
- **Done check:** the video file exists and lasts between 1:50 and 2:00.

## 4. Merge points

Tim merges each track branch into `main` with `git merge --no-ff`; the tracks then run `git merge main`. Nobody rebases a pushed branch. Before each merge point both tracks push and post `DONE:` with their test command.

| Time | Name | Track A brings | Track B brings | Checklist after the merge |
|---|---|---|---|---|
| 16:45 | M0 contract | | | contract done criteria (section 1); both branches merged `main` |
| 21:00 | M1 real topic | A1 to A7, seed v2 released | B1 to B3, B4 started | CI green on `main`; `make seed SEED=v2 checks` OK; B's Compare renders 7 editions on seed v2; `make test` green; the Mainila probe returns "staged" and "reported" |
| 01:00 | M2 real engine | A8 to A11, A12 loaded, seed v3 released | B4 to B7 | `ENGINE=real` Check on one recorded answer works; verdict chips visible in Compare; `make demo-check` green on seed v3; `make check-rules` green |
| 05:00 | M3 freeze | A13 to A16, seed final | B8 to B12 | deployed instance on seed final; `make demo-check` against the URL twice from a fresh load; after this only fixes, each one with a test |
| 07:00 | Recording | numbers checked against `stat` | B13 video helper | Tim records the 2:00 video, Track A checks every number on screen against `stat` and `eval/report.json` |
| 09:30 | Submit | Gemini form text | demo link | Tim submits: video, demo link, repo link, deck PDF; ticks MariaDB, Gemini and Verda; posts the Verda summary link in Verda's Discord |

## 5. Side quest deliverables

We take "Best Use of Gemini API" (c-48, Google DeepMind) and Verda (c-56) (Q11; on Saturday afternoon Gemini replaced Nemotron, in Abdallah's words "stay with gemini since it is a safe bet"). Only what ran gets claimed.

### Gemini, c-48

DeepMind asks for more than an LLM bolted onto an app. The submission has to explain four things: the problem and why it matters, how Gemini is integrated, what is innovative or technically impressive about that use and why Gemini is an important part of the solution.

- Model `gemini-3.8-flash` through the Gemini API in the working solution: it is the judge for every cross-edition pair, the claim splitter for pasted answers in Check and the English gloss under every quoted sentence. It is live in the demo (scene 1:15) and named on screen.
- `docs/GEMINI.md` (Track A, A16), one section per question of the challenge:
  1. Problem: seven language editions tell the same war differently and change over time. Nobody can see where they differ or when a claim was dropped.
  2. Integration: model id, endpoint and SDK (`openai` client on the OpenAI-compatible endpoint), the three prompts, JSON-only answers with one retry, the verdict cache keyed by prompt version, rate limiting and retries (token bucket, backoff on 429 and 5xx, fallback chip "candidate, not judged"), latency per call.
  3. What is technically interesting: vector search in MariaDB finds the right neighbourhood but the exact twin only 57 % of the time at rank 1, so Gemini decides between the top 5 across seven languages and pulls out the numbers and terms that differ; every verdict sits next to the two original sentences and their `?oldid=` links.
  4. Why Gemini matters here: without it there are candidates but no labels, no glosses and no Check. Measured, not claimed: the gold set of 40 to 60 human-labelled pairs, prompt v1 vs v2 with accuracy and kappa per language, plus the Nemotron comparison if A10 step 5 ran.
- Form text, about 120 words, written from GEMINI.md by Tim at 09:00, following the same four points.

### Verda, c-56

- The GPU batch job that embeds every distinct sentence of the Winter War history and the long-lived Finnish lives from M with bge-m3, plus the CPU instance that serves the public demo with MariaDB.
- `docs/VERDA.md` (Track A, A6 and A16): why compute was needed (Ollama on the laptop does 18 sentences/s), instance types, setup minutes, sentences/s on the GPU, number of vectors, cost in credits, what failed. Then the path to scale: the same job over all 568,416 articles of dataset L and more language editions, re-embedding only new distinct sentences each night. Reads and compares only; no automated edits at any scale.
- A post in Verda's Discord channel with the link to VERDA.md and the demo URL; Verda ticked on the submission form.
- If the GPU job did not run by 19:30: no Verda claim. The CPU demo host alone is not enough to claim the prize.

## 6. Cut order

If a merge point slips by more than 45 minutes, cut from the top of this list until the plan fits again. Tim decides.

1. Atlas (B10, A13).
2. Ask (B9).
3. Sources (B8, A14).
4. Verda bulk embedding of M lives (A12 step 4); keep the 100-article subset embedded locally.
5. Live Check on stage; keep recorded runs replaying from the database.
6. Exact bisects beyond the two Mainila edits (en 2009, ru 2014).
7. Glosses beyond the rows shown in the demo.
8. Deploy on Verda (B12); the demo link then points to the video and the repo.

Never cut: Compare, Time, Dropped here alive there, Check with recorded runs and the Gemini judge, the measured agreement number, Under the hood, the footer and the rules of section 0.

## 7. Kickoff prompts

Paste the prompt of your track into your coding agent as its first message. Each agent starts with only the repo.

### Track A

```text
You are the coding agent for Track A "data and engine" of Parallax, our MariaDB entry at Junction 2026. Deadline Sunday 10:00 Helsinki time.

1. git fetch && git switch track-a && git merge origin/main. Work only on branch track-a and push after every task.
2. Read parallax/PLAN.md in full, then WORKING.md. Section 0 has the rules, section 1 the contract, section 2 your tasks A1 to A16 in order. Read parallax/contract/ (schema.sql, engine.py, openapi.yaml, SEED.md) before writing code.
3. You own parallax/pipeline/, parallax/engine/, parallax/eval/, parallax/docs/VERDA.md, parallax/docs/GEMINI.md and parallax/data/ (gitignored). Never edit parallax/api/, parallax/web/, parallax/e2e/ or parallax/contract/. If the contract needs a change, stop and tell your human, who asks Tim.
4. Setup: cd parallax && cp .env.example .env (your human pastes GEMINI_API_KEY, which Tim sent by DM; never commit or print it), uv sync, make db-up seed-mini test-contract.
5. For each task: write the test first, implement, run the done check from the plan exactly, commit with a one-line lowercase message of 2 to 5 words (for example "add wikitext parser"), push, then report to your human in the form "DONE: A3 on track-a, <command> passes (<numbers>)".
6. Rules you never break: never write to Wikipedia; every Wikimedia request through pipeline/wapi.py with the User-Agent from section 0, at most 3 in parallel, cached under parallax/data/raw/; never read or store user names from M or the API; no secrets or data in git; no home paths in files; neutral wording in anything the UI could show.
7. Long jobs (fetch, M lives, embedding, judge) run in the background with progress lines; meanwhile continue with the next task that does not depend on them.
8. Verda: at 17:00 ask your human to start the GPU instance (A6). If no vector came back from it by 19:30, switch to EMBED_BACKEND=ollama, note it in docs/VERDA.md and go on.
9. Merge points: 21:00 (seed v2 released), 01:00 (seed v3), 05:00 (seed final). Before each, push and post DONE with the commands that passed. After Tim merges, run git merge origin/main.
10. If a task runs more than 30 minutes over its estimate, tell your human and propose what to cut from section 6.
Start with A1.
```

### Track B

```text
You are the coding agent for Track B "app" of Parallax, our MariaDB entry at Junction 2026. Deadline Sunday 10:00 Helsinki time.

1. git fetch && git switch track-b && git merge origin/main. Work only on branch track-b and push after every task.
2. Read parallax/PLAN.md in full, then WORKING.md. Section 0 has the product, the demo script and the rules, section 1 the contract, section 3 your tasks B1 to B13 in order. Read parallax/contract/ (schema.sql, engine.py, openapi.yaml, examples/, SEED.md) before writing code.
3. You own parallax/api/, parallax/web/, parallax/e2e/, parallax/deploy/ and parallax/docs/DEMO.md. Never edit parallax/pipeline/, parallax/engine/, parallax/eval/ or parallax/contract/. Use the engine only through contract.engine.get_engine(). If the contract needs a change, stop and tell your human, who asks Tim.
4. Setup: cd parallax && cp .env.example .env (GEMINI_API_KEY can stay empty until the 01:00 smoke test, then your human pastes the key Tim sent by DM), uv sync, make db-up seed SEED=v1, cd web && npm ci. Until the 21:00 merge you work on seed v1 with ENGINE=fake; you never wait for Track A.
5. For each task: write the test first, implement, run the done check from the plan exactly, commit with a one-line lowercase message of 2 to 5 words (for example "add compare view"), push, then report to your human in the form "DONE: B3 on track-b, <command> passes".
6. UI rules you never break: words "differs", "not found in", "uses the term", "cites mostly", "stopped saying"; never "biased", "propaganda", "false", "wrong" or any ranking of editions; no editor names; glosses labelled "machine translation"; every quote links to its ?oldid=; the footer from section 0 on every page; Codex 2.7.0 only through the import map from jsDelivr, never copied into the repo or the bundle; no Wikipedia logo, globe, cdxIconLogo icon, Vector chrome or "Wiki" in the name; no button that edits anything, only "Open on <lang>.wikipedia" links. Run make check-rules before every push.
7. No secrets in git, no home paths in files. Every view's SQL is stored in api/queries/ and every response carries the sql array.
8. Merge points: 21:00 (switch to seed v2), 01:00 (seed v3, ENGINE=real smoke test), 05:00 (freeze, deployed URL passes make demo-check twice). Before each, push and post DONE with the commands that passed. After Tim merges, run git merge origin/main.
9. If a task runs more than 30 minutes over its estimate, tell your human and propose what to cut from section 6.
Start with B1.
```
