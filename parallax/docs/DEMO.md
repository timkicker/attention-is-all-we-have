# Demo check

`make demo-check` walks the two minute demo script of [PLAN.md](../PLAN.md) section 0 in a browser and fails loudly when a step no longer shows what the script says. Run it before every recording and after every deploy.

## Run it locally

```
make seed               # SEED=v4 by default; /api/health then reports the seed the database was loaded from
make demo                # builds web/dist, checks the AI answers with the real engine once, serves on API_PORT (default 8000)
make demo-check          # in a second shell, against http://127.0.0.1:$(API_PORT)
```

Against the deployed instance:

```
BASE_URL=https://<host> make demo-check
```

Each step prints one line, then a total:

```
passed  0:00 title: the wordmark Parallax (401 ms)
passed  0:08 compare: the Mainila row in every edition, terms and numbers that differ (2320 ms)
...
demo-check: 7 of 7 steps passed (passed)
```

A failing step prints `FAILED` with the first line of the error, the others still run and the command exits with an error. Playwright keeps a trace of the failed step under `e2e/results/`.

## What each step asserts

| Script time | Step | Asserted on screen |
|---|---|---|
| 0:00 | Title | page title and wordmark "Parallax" |
| 0:08 | Compare | the Mainila row has one cell per edition of the topic; de "inszenierte", en "reported" and the sv term of the seed; the seed's verdict chip ("partly the same" on v4); the Finnish dead row shows fi "26 662" and "number differs" in the editions of the seed (de, en, uk on v4) |
| 0:30 | Time | for the fi Mainila sentence alive before the change, the en cell reads "the Soviets staged" before it and "... was reported" after it, life bars are drawn, and from seed v3 on the edit comment of the change is on the bar |
| 0:55 | Dropped | with the edition filter on Russian (paging on while needed), the ru card for "инсценированный советской стороной" with its date and the oldid of its last revision, the de chip, and from seed v3 on the Finnish scale line |
| 1:15 | Check | the recorded answer about Mainila with its model, a chip "en: stopped saying (year)" and a "not found in" chip |
| 1:35 | Under the hood | one statement with both `FOR SYSTEM_TIME AS OF` and `VEC_DISTANCE_COSINE`, its time and rows, the scale grid |
| 1:50 | Footer | the footer text, "Evidence, not edits.", an "Open on fi.wikipedia" link to an oldid and no edit button |

The values the audience reads live in `e2e/demo-facts.ts`, one entry per seed: sentences, terms, dates, edit comments and Wikipedia revision ids. Row ids are claim hashes, which depend on how a seed split the text, so the walk finds the rows through `/api/compare` (the fi sentence of the section that contains the given words) and takes the number of editions from `/api/topics`. The step reads the seed from `/api/health` and stops with "no demo facts for seed ..." on any other seed.

The recorded answers come from `contract/fixtures/answers.json` (A15, `make answers`). `make demo` checks them with `ENGINE=real` when the database holds no recorded answer yet, so it needs `GEMINI_API_KEY` in `.env` once per fresh seed load. An answer whose check fails is tried three times, then skipped.

`make e2e` leaves the demo walk out (it is tagged `@demo`) and runs the other specs on seed-mini in a database of its own.
