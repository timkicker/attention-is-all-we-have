# Performance

Every number on this page comes from `scripts/loadtest.py` or a profiler run on one laptop on 14 November 2026. Nothing is estimated. Where a number is missing, the page says what would be needed to get it.

## Setup

| | |
| --- | --- |
| Machine | AMD Ryzen 7 7840U w/ Radeon 780M Graphics, 16 logical CPUs, 60 GiB RAM, Linux 7.2.6-arch2-1, Python 3.12.13 |
| Server | one uvicorn process, one worker, a fresh seeded store per run, Valio in replay mode. The tables come from main with the lock fix (`lock shared sqlite connections`) before `harden key binding checks` |
| Command | `cd validio/src/backend && uv run python ../../scripts/loadtest.py --agents 1 10 50 --rounds 5` |
| Wide mix | the same with `--mix wide` |

Each of the N agents has its own Holder and runs scene 2 five times in a row: nonce, `POST /agent/v1/requests`, nonce, `POST /agent/v1/orders`, `GET /agent/v1/orders/{id}`. All N agents start at once. The client measures each HTTP call. The server process counts the time callers waited for the three locks in front of the SQLite connections and every question it sends to Valio.

The laptop was not idle. Other jobs ran on it during the tests. In the last run its load average went from 4.4 to 27.0. That is why throughput is given as a range over all runs on the same code. Later that night the machine reached 100 °C and heavy jobs were limited to two shared slots, so no more runs at N=50 were made after the ones on this page. They ran on a machine that was already hot and busy. Whether an idle and cool machine would give more is not measured. One run at N=1 and 10 on main after `harden key binding checks` gave 72.2 and 104.8 requests per second with no error, inside the range below.

## Results

Run with the lowest load, scene 2:

| N | Scenes | Placed | Errors | Wall time | Requests/s | Scenes/s |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 5 | 5 | 0 | 0.33 s | 75.7 | 15.13 |
| 10 | 50 | 50 | 0 | 2.31 s | 108.1 | 21.62 |
| 50 | 250 | 250 | 0 | 12.26 s | 101.9 | 20.39 |

Latency per route in the same run, p50 and p95 in milliseconds:

| Route | N=1 | N=10 | N=50 |
| --- | --- | --- | --- |
| `GET /agent/v1/nonce` | 1.5 / 21.7 | 2.8 / 18.8 | 87.6 / 223.4 |
| `POST /agent/v1/requests` | 32.4 / 115.2 | 225.6 / 423.2 | 852.6 / 2018.5 |
| `POST /agent/v1/orders` | 5.9 / 7.1 | 177.4 / 386.4 | 814.9 / 2124.2 |
| `GET /agent/v1/orders/{id}` | 1.4 / 1.8 | 4.6 / 8.6 | 65.9 / 184.1 |

Over five runs on the same code, N=10 reached 65.4 to 134.1 requests per second (13.1 to 26.8 scenes per second) and N=50 reached 42.4 to 128.6 (8.5 to 25.7 scenes per second). The two lowest values come from the run with the load average of 27. At N=50 in that run the p50 of `POST /agent/v1/requests` was 1980.1 ms and the p95 was 4485.7 ms.

From 10 agents on the throughput no longer grows and only the latency does. The reason shows in the lock counts.

| Lock, N=50, run above | Acquired | Waited | Waited in total | Longest wait |
| --- | --- | --- | --- | --- |
| order service | 750 | 511 | 436.3 s | 5475.0 ms |
| order store connection | 3250 | 145 | 0.08 s | 3.1 ms |
| steady runtime | 2000 | 571 | 2.6 s | 44.7 ms |

SQLite itself never reported `database is locked`. The waiting happens one level up in `OrderService.lock`. `request_supply` holds that lock for its whole length, including Cedar and the questions to Valio. One request at a time decides, however many agents are connected. This is what keeps idempotency keys and request ids consistent today, so it was not changed tonight.

The wide mix sends one request with five lines (milk by text, 466375, 463968, 471376 and mozzarella by text). It goes to a person every time because 1386.08 EUR is over the auto limit, so the agents order nothing.

| N | Requests | Errors | p50 / p95 `POST /agent/v1/requests` | Requests/s |
| --- | --- | --- | --- | --- |
| 1 | 5 | 0 | 190.2 / 391.4 ms | 7.8 |
| 10 | 50 | 0 | 1980.3 / 2153.5 ms | 9.8 |
| 50 | 250 | 0 | 9431.8 / 10440.5 ms | 9.3 |

## Bug found under load

The first run with 50 agents crashed the server with `sqlite3.DatabaseError: no more rows available` in `Store.new_request`. The order store and the ledger each share one SQLite connection between all worker threads. Writes in the order store took a lock but reads did not. The ledger had no lock at all, so two threads could start `BEGIN IMMEDIATE` on the same connection. `tests/test_store_threads.py` reproduces both (16 threads on the store and 12 on the ledger, red in each of three runs before the fix). The commit `lock shared sqlite connections` makes reads take the store's lock and gives the ledger its own. Since then no run has had an error.

## Valio call budget

A request may ask Valio about at most 40 distinct product ids (`CallBudget`, `VALIO_MAX_IDS_PER_REQUEST`). One call may carry up to 1000 ids because Valio rejects longer lists. The 40 is a limit per request and not per call. Under load the server counted every call it sent.

| Mix | Calls per check | Ids per call, highest | Distinct ids per check, highest |
| --- | --- | --- | --- |
| scene 2 | 2 to 4 | 12 | 12 |
| wide | 14 | 12 | 26 |

A check is one request or the second look Validio takes before it places an order. In scene 2 a request costs 4 calls (price and availability for 12 ids, then both again for the chosen product) and the confirmation costs 2 more. The counts are the same at N=1, 10 and 50, so concurrency does not change what reaches Valio. No run came near 40 ids. `test_budget_blocks_41_ids` in `tests/test_valio.py` checks that the 41st id is refused before any call goes out.

## Where the time goes

A cProfile run over 20 scene-2 rounds in process (the profiler slows everything, so only the shares count) puts most of `request_supply` in the rules. Cedar is asked 26 times per request through `cedarpy.is_authorized` and that adds up to about half of the request. Building the settings from the environment and the `.env` file took about a fifth as long as `request_supply` because the order clock rebuilds them on every read (26 times per scene).

A cache for the settings removed that share in the profile but did not move the throughput. Three runs with the cache gave 100.5 to 142.8 requests per second at N=10, against 113.5 to 134.1 without it. The rule was to fix a hot path only when the fix is surgical and clearly pays off, so it was not committed. The lock is the more likely place to win throughput, by no longer holding `OrderService.lock` around Cedar and the Valio calls. That is not measured. It needs a different way to keep idempotency safe and is left open.

## What replay does not measure

- Valio's own latency. In replay a question to Valio is a file read. With the live test API every call adds its network time. In today's code that time is spent inside the service lock. A scene-2 request makes 4 calls in a row and a wide one 14. How long that takes needs a run against the test API, which was not done for this page.
- Valio's rate limits and what it does with many parallel callers.
- Gemini. The load test uses no model, the agents are scripted HTTP clients.
- More than one server process. Every run used a single uvicorn worker.
- Postgres. The store here is SQLite in a local file.

## Cost

Only Modal prices can be cited. Read on https://modal.com/pricing on 14 November 2026:

| Resource | Price |
| --- | --- |
| CPU | $0.0000131 per physical core per second (a core is 2 vCPU, at least 0.125 cores per container) |
| Memory | $0.00000222 per GiB per second |
| Nvidia H200 SXM | $0.001261 per second |
| Nvidia H100 SXM5 | $0.001097 per second |
| Starter plan | $30 of compute free per month |

Per hour that makes $0.0472 for one core, $0.0080 for one GiB and $4.54 for one H200.

What a scene costs on Modal is still unknown. The throughput above comes from a laptop core and nobody has run Validio on Modal yet, so dividing the two would be a guess. The Gemma reader is not deployed either (Modal needs a payment method for its GPUs), so there is no measured GPU time per description.

The cost of Gemini is unknown until a live run. The transcripts in `artifacts/agent/` come from the fake twin. Their size says nothing about the tokens a real model would read and write, because Gemini sees the same answers but writes its own calls and text. `test_gemini_buyer_scene2_three_runs_same_order` is the place to measure it once a key exists.
