# Demo check

`make demo-check` walks the two minute demo script of [PLAN.md](../PLAN.md) section 0 in a browser and fails loudly when a step no longer shows what the script says. Run it before every recording and after every deploy.

## Run it locally

```
make seed SEED=v3        # or SEED=v1 until v3 is released
make demo                # builds web/dist, records the example answers once, serves on API_PORT (default 8000)
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
| 0:08 | Compare | the Mainila row has one cell per edition (7 on seed v3); de "inszenierte", sv "kunnat bevisas", en "reported"; a "same claim" chip; the Finnish dead row shows fi "26 662" and "number differs" in sv and en |
| 0:30 | Time | the en Mainila cell reads "the Soviets staged" before the change and "an incident was reported" after it, life bars are drawn, and on seed v3 the edit comment of the change is on the bar |
| 0:55 | Dropped | the ru card for "инсценированный советской стороной" with its date and the oldid of its last revision, "de: same claim", and on seed v3 the Finnish scale line |
| 1:15 | Check | a recorded answer with its model, a chip "en: stopped saying (year)" and a "not found in" chip |
| 1:35 | Under the hood | one statement with both `FOR SYSTEM_TIME AS OF` and `VEC_DISTANCE_COSINE`, its time and rows, the scale grid |
| 1:50 | Footer | the footer text, "Evidence, not edits.", an "Open on fi.wikipedia" link to an oldid and no edit button |

The values that depend on the data live in `e2e/demo-facts.ts`, one row per seed. The step reads the seed from `/api/health` and stops with "no demo facts for seed ..." on any other seed. The v1 row was read off seed v1. The v3 row holds the values the demo script names (en change on 21 Aug 2009, ru change on 9 Jul 2014, seven editions); correct it there if seed v3 differs.

`make e2e` leaves the demo walk out (it is tagged `@demo`), because its facts need seed v1 or v3.
