# Validio

Validio sits between a kitchen's purchasing agent and Valio Aimo's wholesale API. The agent asks for supplies in plain words or by product id and Validio turns that into a typed need, searches its own copy of Valio's catalog and asks Valio's test API for price and availability of the few candidates only. Every fact it uses carries a Fact Grade that says how far it can be trusted (a missing value is never read as a yes). A rule engine (Cedar) then decides whether the agent may order alone, has to ask a person or is blocked, so no model output can move money on its own. Each decision ends up as one sentence in a hash-chained ledger that the kitchen and Valio read the same way.

The full plan with the reasoning behind each part is in [PROJECT_BLUEPRINT.md](../PROJECT_BLUEPRINT.md). The Hard Lines are listed in [docs/RULES.md](docs/RULES.md) and the click-through for the demo in [docs/DEMO.md](docs/DEMO.md).

## Setup

You need Python 3.12 with uv, Node 20 and the three Valio data files from the resource portal. Every command runs from `validio/`.

```sh
make setup                  # .env from .env.example, uv sync, copy and check the Valio files, build data/catalog.db
make seed                   # demo state: kitchen hotel-espoo, Spend Pass M-1, 8 weeks of simulated history
make test                   # guard checks, ruff, pytest (no network)
make agent SCENE=2          # the kitchen's agent runs scene 1, 2 or 3 and prints every tool call
make dev                    # the API on http://127.0.0.1:8410
make demo                   # builds the web app, seeds and serves both on http://127.0.0.1:8410
make demo-check             # every demo scene end to end on its own server on port 8418
```

`make demo` builds the web app on its fixture unless it runs as `VITE_API=live make demo`. `make demo-check` ends with `ALL SCENES OK` and leaves a running demo alone.

`make setup` reads the Valio files from `RAW` (default is the folder on the build machine), so elsewhere it is `make setup RAW=/path/to/files`. The files are checked against their sha256 before anything is indexed.

The web app is a separate SvelteKit project:

```sh
cd src/frontend
npm ci
npm run kit                 # fetches the Arlen ui-kit at a pinned commit into vendor/ (gitignored)
npm run dev                 # http://127.0.0.1:5410
```

Without anything else the pages run on the fixture in `src/lib/api/mock.ts`. With `VITE_API=live npm run dev` they ask the backend on port 8410 instead.

`make record` calls Valio's test API with the key from `.env` and stores the answers. `make test-live` runs the tests that need the network (Valio's test API, plus the Gemma reader when `MODAL_GEMMA_URL` is set).

## Architecture

![One request through the system](../docs/img/sequence.png)

The agent calls `request_supply`. Validio checks the Spend Pass (an SD-JWT bound to the agent's key) and parses the need. It searches the catalog without any API call and sends at most 40 product ids to Valio for price and availability. It then grades every fact, ranks the safe options and asks Cedar for the decision. The decision goes into the Open Ledger and back to the agent, which confirms it with `confirm_order`. If Cedar says "ask", the owner answers on the phone. Before anything is placed Validio asks Valio again and refuses when the price rose by more than 2 % or a line can no longer be delivered.

Supplier text never reaches a decision. The reader in `validio/reader/` looks at descriptions and flags text that talks to AI agents, but its output is only shown. A test checks that matching, trust and policy never import it. A second test with a control proves that the comparison would notice if someone wired it in.

## Folders

| Path | What is in it |
|:---|:---|
| `src/backend/validio/catalog/` | the SQLite index over Valio's product file, labels, substitutes and the planted line kept in its own table |
| `src/backend/validio/valio/` | the client for Valio's test API with record and replay, plus the call budget |
| `src/backend/validio/trust/` | Fact Grades and the claim check |
| `src/backend/validio/matching/` | need parsing, Best Pick ranking, Safe Swap and Split Fill |
| `src/backend/validio/policy/` | the Spend Pass (SD-JWT) and the Cedar rules in `policies.cedar` |
| `src/backend/validio/orders/` | the order service that re-asks Valio before it places anything |
| `src/backend/validio/standing/` | Steady Orders and Drift Watch |
| `src/backend/validio/audit/` | the Open Ledger |
| `src/backend/validio/reader/` | the reader of supplier text (fake by default, Gemma on Modal when configured) |
| `src/backend/validio/agent/` | the kitchen's purchasing agent and the terminal pane for the demo |
| `src/backend/validio/api/` | the FastAPI app |
| `src/backend/validio/demo/` | the planted line, the simulated order history and the seed |
| `src/frontend/` | the web app: inbox, decision view, phone approval, Steady Orders, Open Ledger |
| `src/cloud/` | the Modal app for the Gemma reader |
| `scripts/` | data import, indexing, recording, seeding, the agent runner and the guard checks |
| `data/` | Valio's files, the catalog index, recorded answers and the local database (gitignored) |

## Real and simulated

All 17,546 products come from Valio's files with their claims, allergens, substitutes, delivery reliability and carbon values. Every price and availability answer comes from Valio's test API at `junction26.valioaimo.fi` for customer `hotel-espoo`. The demo clock is fixed at 14 November 2026 10:00 Helsinki time, which is why the Terminal products with a cut-off on 12 November drop out.

The screen marks everything that is simulated. Mozzarella 466375 runs out in scene 3 although Valio really has it in stock. The 8 weeks of order history behind the Steady Order with 400 guests a week are invented. The line in 463047's description that talks to AI agents was planted by us and is kept in its own table apart from Valio's text. The kitchen's agent runs on a fake model with fixed answers when no Gemini key is set. The Gemma reader is not deployed because Modal needs a payment method for its GPUs, so the fake reader answers.

## Replay

Every answer from Valio's test API is stored under `data/cache/valio/<endpoint>/<date>/` and named by the SHA-256 of endpoint, date and the sorted product ids. With `VALIO_MODE=replay` (the default) the client answers only from those files and never opens a connection. A question it has no answer for raises `ReplayMiss`, so a missing recording shows up as an error and never as a quiet empty result. `VALIO_MODE=record` calls the API and saves the answers and `live` calls it without saving. Valio's data and the recordings never go into git because Valio allows their use only for this challenge.

## Guard checks

`make guards` runs two scripts over every file git would see. `make test` runs them first.

`scripts/check_no_secrets.sh` fails on a Valio API key, a Gemini key, a private key or a JWK with its private part. A committed `.env` fails it too. It prints file and line, never the secret.

`scripts/check_forbidden_hosts.sh` fails when the address of Valio's real webshop or its production API appears anywhere outside `docs/`. Validio only ever talks to the test API.
