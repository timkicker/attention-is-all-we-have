# Seeds

Every seed is a SQL file for schema v1 (`contract/schema.sql`). Data never goes into a commit except seed-mini.

## Loading

```sh
cd parallax
cp .env.example .env          # optional, the defaults work for the local container
make db-up                     # MariaDB 12.3.3 on 127.0.0.1:3307
make seed-mini                 # drop all tables, apply schema.sql, load seed-mini.sql
make seed SEED=v1              # download release parallax-seed-v1 to data/ if missing, drop all tables, load
make test-contract
```

`scripts/load_sql.py` does the loading through pymysql with the settings from `.env`, so no MariaDB client is needed on the host. It splits statements on a semicolon at the end of a line, which holds for `schema.sql`, seed-mini and `mariadb-dump` output. Without a `.env`, the password is `parallax`, the same default `docker-compose.yml` uses.

Every session sets `time_zone='+00:00'` and `mhnsw_ef_search=1000` (`contract.db.connect()` does both). `AS OF TIMESTAMP` needs a full datetime literal such as `'2008-06-01 00:00:00'`; a bare date fails with error 1525.

## seed-mini.sql (committed, used by CI)

- **Source:** the Saturday spike database (container `wikispike`, schema `lens`): Winter War in fi, sv, de, en, ru and et, five yearly snapshots (2006, 2010, 2014, 2018, 2022) plus the current revision, bge-m3 vectors from Ollama.
- **Cut:** claim rows in the sections about Mainila and the casualty figures (list in `scripts/build_seed_mini.py`), plus every row elsewhere that mentions Mainila or one of the Finnish casualty figures. 413 claim rows with all their lives, 46 section_text rows, 6 pages, 38 revisions (the snapshots plus three demo revisions), 12 verdicts and 16 glosses.
- **Conversion:** `sentence` becomes `claim` with `time_precision='snapshot'`, `topic_id='winterwar'`, `h` recomputed with `contract.engine.claim_hash`. `born_rev` is the snapshot revision at `row_start`, `died_rev` the snapshot revision at `row_end` (NULL while alive). `died_comment` is NULL at snapshot precision. Vectors are written as `FROM_BASE64(...)` of little endian float32.
- **Probes it answers:** en `AS OF '2008-06-01 00:00:00'` says "the Soviets staged the Shelling of Mainila", `AS OF '2012-06-01 00:00:00'` says "a border incident was reported". ru drops "инсценированный советской стороной" between the 2014 and 2018 snapshots.
- **Verdicts and glosses** come from `contract/fixtures/engine/judge.json` and `gloss.json` with model `fake-judge` and `fixture-gloss`. Glosses are machine translation.
- **No user names:** the spike never stored any, and `revision` has no user column.
- **Rebuild:** `SPIKE_PASSWORD=... uv run python scripts/build_seed_mini.py SPIKE_DIR` where `SPIKE_DIR` holds the spike's `out/` and `raw/` folders. Then `make seed-mini` and `uv run python scripts/build_engine_fixtures.py` if the fixtures change.

## Engine fixtures (`contract/fixtures/engine/`)

| File | Key | Value |
|---|---|---|
| `embed.json` | `claim_hash(text)` | `{text, copy_of: "lang:h", emb}`, `emb` base64 float32, a copy of that seed row's vector |
| `split.json` | `claim_hash(answer)` | `{text, claims: [...]}` |
| `judge.json` | `"<claim h>:<candidate h>"` | `{a_lang, b_lang, label, numbers, terms, note}` |
| `gloss.json` | `"<lang>:<h>"` | `{text_en}` |

They cover the demo path: one recorded answer about Mainila with three claims whose vectors are seed rows' vectors (so Check finds real rows in fake mode), the fi anchor rows for Mainila and the Finnish dead with their matches, and glosses for the sentences shown in the demo.

## API examples (`contract/examples/`)

Built from seed-mini rows for compare, timeline, dropped, check and ask. The numbers in sources, atlas and stats only show the shape until Track A computes the real ones.

## Bigger seeds

| Seed | Made by | Release |
|---|---|---|
| `v1` | contract: the whole spike (7,116 claim rows, 784 section rows) converted as above, `mariadb-dump --dump-history` | `parallax-seed-v1` |
| `v2` | Track A at M1: full Winter War, 7 editions | `parallax-seed-v2` |
| `v3` | Track A at M2: plus verdicts, glosses, M lives, atlas | `parallax-seed-v3` |
| `final` | Track A at 04:30 | `parallax-seed-final` |

Releases: `gh release create parallax-seed-vN data/seed.sql.gz --title "seed vN" --notes "<row counts>"`, downloaded by `make seed SEED=vN`.
