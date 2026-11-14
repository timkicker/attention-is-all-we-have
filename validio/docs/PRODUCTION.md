# Path to production

This page says what Validio needs before a wholesaler like Valio Aimo could run it for real kitchens. It covers what already holds today, what is still demo only and the order in which we would close the gaps. The threats and their tests are in [SECURITY.md](SECURITY.md), and the rules are in [RULES.md](RULES.md).

## What a wholesaler gets

- **One open door for every agent.** The same tools are offered over MCP at `/mcp/k/<account>/` and over HTTP with OpenAPI 3.1 under `/agent/v1/k/<account>`. Any vendor's agent can connect without a Valio-specific SDK ([AGENTS.md](AGENTS.md)). `examples/agent_client.py` is a complete third-party agent in one file.
- **Nothing real exposed.** Agents talk to Validio, never to Valio's systems. Validio asks Valio's API for price and availability of at most 40 products per call. It never calls the webshop, which a CI check enforces. The agent's model never sees supplier text. Each decision shows only the Spend Pass fields it needs.
- **Open standards.** These are:
  - SD-JWT for the kitchen's signed permission (the Spend Pass)
  - ES256 keys
  - Cedar for the rules
  - a SHA-256 hash chain with a signed head for the log
  - MCP and OpenAPI for the agent interface

  None of them is ours to lock in.

## Confidentiality, integrity, availability

| | Holds today | Needed for production |
|:---|:---|:---|
| **Confidentiality** | The agent's model gets no supplier text (`agent/tools.py`). The Spend Pass discloses only budget, cap and diet per decision. The approval code is stored as an scrypt hash, with 5 tries. The kitchen token is a cookie. Accounts are kept apart by a 128-bit id plus a pass check on every read. Secrets live only in `.env`, and `check_no_secrets.sh` guards git. | Named approvers with their own PIN or passkey in place of one shared code. Two-factor login. A fresh signing key per kitchen instead of a copy of the template key. Try counters stored on disk. Secrets in a managed vault. |
| **Integrity** | The Spend Pass is signed, bound to the agent's key, and checked with a nonce and audience. Cedar forbid rules always win. Totals are recomputed from Valio's price. Valio is asked again before anything is placed, and a price rise over 2 % or a missed delivery refuses the order. Every decision is chained into the activity log with a signed head (`GET /api/ledger/head`). | The weekly limit moved into Cedar next to the other rules. The signed head pinned by Valio automatically, for example once an hour. The signing key in an HSM or KMS rather than `data/keys/`. Requests and orders chained like the log. |
| **Availability** | Valio's answers can be replayed from a recorded cache, so the demo never needs the network. A timeout or 5xx from Valio is retried once and then fails closed: nothing is ordered and the log says why. Every page has an error state with Retry. | Postgres in place of SQLite, with backups and point-in-time restore. A shared nonce store so several server processes can run. A rate limit on nonces. Health checks that ask Valio. A status line for the kitchen when Valio is slow. |

## Steps

1. **Pilot with one kitchen group.** Run on Valio's test API with real catalog data for a few weeks. Approvals go to named people on their phones. The activity log is exported weekly for Valio to compare with its own order records.
2. **Harden identity.** Add per-person approvers and passkeys, a key per kitchen, and secrets in a vault. Run an external security review of the Spend Pass and approval paths.
3. **Scale the store.** Move to Postgres for orders, the log and nonces (`orders/store.py`, `audit/log.py`, `policy/mandate.py`). Run two or more server processes behind a load balancer and take daily backups.
4. **Connect to Valio's production order API.** Only with Valio's agreement and a separate key. Replay stays for tests and demos. The forbidden-host check stays until Valio approves the production address.
5. **Open the door to more agents.** Publish the OpenAPI and MCP descriptions, keep `AGENTS.md` checked by its test, and add vendor sandboxes using the template kitchen.

## Run it yourself

The quick look without keys and the full setup are in the [README](../README.md#setup). For a public deploy set `VALIDIO_PUBLIC=1`. The app then refuses to start without `VALIDIO_APPROVE_CODE` and `VALIDIO_KITCHEN_TOKEN`, and nobody counts as local. `make modal-deploy` builds the web app and deploys both on Modal.
