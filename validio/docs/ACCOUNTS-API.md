# Accounts API

The contract between the backend and the web app for kitchen accounts. JSON is camelCase, money is
integer cents, times are ISO 8601 with offset. Every error is `{"detail": "<one sentence>"}`.

## Session

* Cookie `validio_session`: httponly, `secure` on https, `samesite=lax`, 12 h. The web app never sees
  or sends it by hand (`credentials: "include"` on fetch is enough).
* Every `/api` route except health, signup, login, demo and the phone link answers **401** without a
  valid session when the caller is not on this machine. The web app sends the person to the login page
  on any 401.
* A caller on this machine without a session still reaches the old single kitchen (`data/validio.db`),
  so `make dev`, the CLI agent and the old tests keep working. `GET /api/account` answers 401 there too,
  so the web app shows the login page.
* The demo token (`X-Demo-Token`) and the kitchen token are gone for the web app. Demo controls work for
  demo accounts only.

## Account

```
Account = {
  id: string,                 // "k-3f9a1c2e", also used in the agent URLs below
  name: string,               // "Hotel Espoo kitchen"
  email: string | null,       // null for a demo copy
  customerNumber: string,     // Valio customer number, read only after signup
  deliveryAddress: string,    // "" until set
  isDemo: boolean,
  demoCode?: "246810",        // only on demo copies: the approval code, shown in the demo bar on purpose
  setup: {                    // the Inbox checklist; a fresh demo copy has kitchen and rules true
    kitchen: boolean,         // name and delivery address saved
    rules: boolean,           // Rules saved once (until then every order needs approval)
    agent: boolean,           // an agent is connected (active or paused)
    done: boolean             // all three
  },
  agent: AgentState,          // see Agent
  createdAt: string
}
```

| Method | Path | Body | Answer |
| --- | --- | --- | --- |
| POST | `/api/account/signup` | `{name, email, password, customerNumber, approvalCode}` | 201 `Account`, sets the cookie |
| POST | `/api/account/login` | `{email, password}` | 200 `Account`, sets the cookie |
| POST | `/api/account/logout` | none | 204, clears the cookie |
| POST | `/api/account/demo` | none | 200 `Account`, sets the cookie |
| GET | `/api/account` | none | 200 `Account`, 401 without a session |
| POST | `/api/account/phone-link` | `{path}` e.g. `"/approve/R-2"` | 200 `{url}` |
| GET | `/api/account/open/{token}` | none | 303 to the `path`, sets the cookie |

* Signup: `password` at least 8 characters, `approvalCode` exactly 6 digits, `customerNumber` 1 to 20
  digits, `email` unique (409 "an account with this email exists"). 422 for a field that does not fit,
  `detail` names the field.
* Login: 401 "wrong email or password" for both cases. Five wrong tries from one client or for one email
  in 15 minutes answer 429.
* Demo: a browser that already holds a demo session gets the same copy back (reload keeps the state). A
  new browser gets a fresh copy of the filled demo kitchen: the five scenes played, rules saved, no
  agent connected yet (the person presses "Connect the demo agent", then Allow). Copies older than 48 h
  are deleted.
* Phone link: a one-time link, valid 10 minutes, that logs the phone into the same account and opens
  `path`. The web app turns `url` into a QR code or a copy button.

## Agent

```
AgentState = {
  state: "none" | "pairing" | "consent" | "active" | "paused",
  pairing?: {code: string, expiresAt: string, mcpUrl: string, apiUrl: string},   // state "pairing"
  consent?: {name: string, keyId: string, may: string[]},                          // state "consent"
  agent?: {name: string, keyId: string, connectedAt: string, lastUsedAt: string | null,
           passId: string, passVersion: number},                                   // "active" / "paused"
  versions: [{version: number, at: string, why: string}]                           // newest first
}
```

* `code`: 8 characters, letters and digits without look-alikes (`7KQ4-M2XD` shown with a dash, sent
  either way), valid 10 minutes.
* `mcpUrl`: `https://<host>/mcp/k/<accountId>/`; `apiUrl`: `https://<host>/agent/v1/k/<accountId>`.
* `may`: the Rules in words, e.g. `["Order alone up to 1,200.00 €", "Ask you up to 2,000.00 €",
  "Never above 2,000.00 €", "Substitutes from Valio's list"]`.
* `keyId`: the JWK thumbprint of the agent's key, first 8 characters, for the Technical fold.
* `versions[].why`: "Agent connected", "Rules changed", "Diet changed", "Agent disconnected".

| Method | Path | Body | Answer |
| --- | --- | --- | --- |
| GET | `/api/agent` | none | `AgentState` |
| POST | `/api/agent/pair` | none | `AgentState` in `pairing` (a new code each time) |
| POST | `/api/agent/demo` | none | `AgentState` in `consent`: the server's demo agent answered the code (demo copies only) |
| POST | `/api/agent/allow` | none | `AgentState` in `active`; the pass is signed again to the agent's key, version +1 |
| POST | `/api/agent/deny` | none | `AgentState` in `none` |
| POST | `/api/agent/pause` | `{paused: boolean}` | `AgentState` in `paused` or `active` |
| POST | `/api/agent/disconnect` | none | `AgentState` in `none`; version +1, the agent's copy is refused from now on |

* Allow needs no approval code (the person is logged in and the pass is not wider than the saved
  Rules). 409 when there is nothing to allow.
* Paused: every agent call with the pass answers 401 "the kitchen paused this agent" and writes one
  ledger entry. Unpause brings the same pass back, no new version.
* No agent connected (state `none`, `pairing` or `consent`): every agent call with the pass answers 401
  "no agent is connected to this kitchen", no ledger entry.
* The pairing code is kept until it expires, so `GET /api/agent` after a reload still shows it.
  `POST /api/agent/pair` answers 409 while an agent is connected (disconnect first).
* Ledger entries (`kind`): `agent` for connected, paused, resumed, disconnected and refused because
  paused (connected and disconnected name the new pass version in the sentence); `spend_pass` for a
  version from Rules or Diet. `spendPassId` set on all of them, so the Agent page's "See in ledger"
  filters on it.
* Every version, its time and `why` is kept in the kitchen's store (`pass_version`), newest first in
  `versions`. Disconnect signs M-1 again to a key nobody keeps; it never revokes, so the next agent gets
  M-1 back.

Agent side (for any agent, documented in AGENTS.md as well):

| Method | Path | Body | Answer |
| --- | --- | --- | --- |
| POST | `/agent/v1/k/{account}/pair` | `{code, name, publicJwk}` | 202 `{status: "consent"}`, 404 for a wrong or expired code |
| GET | `/agent/v1/k/{account}/pass?code=` | none | `{status: "consent" \| "allowed" \| "denied", spendPass?}` |
| any | `/agent/v1/k/{account}/...` | | the six agent routes of today, per account |
| | `/mcp/k/{account}/` | | the six MCP tools of today, per account |

The old `/agent/v1/...` (with `/agent/v1/pair` and `/agent/v1/pass`) and `/mcp/` keep serving the
local kitchen for `make agent` and the tests. An unknown account in the path answers 404. Over MCP the
kitchen's nonce is the resource `validio://k/<account>/nonce` (the six tools read the account from the URL).

## Rules

What the agent may do, in one place. With `perWeekCents` set, alone and approval count per order and the
week counts every order placed under the pass together (over it: blocked). With `perWeekCents` null, alone
and approval count across the pass's week (orders already placed add up), as before.

The demo kitchen starts with: alone up to 1,200.00 €, approval up to 5,000.00 €, per week 8,000.00 €,
substitutes `extra` 5 % (`api/settings.DEMO_RULES`). So the example request (1,000 l milk, 1,010.00 €) is
ordered alone, lowering alone to 800.00 € makes the same request wait, and 246810 approves it.

```
Rules = {
  aloneUpToCents: number,        // orders alone up to this
  approvalUpToCents: number,     // needs approval up to this, blocked above
  substitutes: "off" | "listed" | "extra",
  maxExtraPct: number,           // only with "extra": a swap may cost up to this % more (0 to 20)
  perWeekCents: number | null,   // all orders under the pass together; null: no weekly limit (see above)
  saved: boolean,                // false until saved once: everything needs approval
  passVersion: number
}
```

| Method | Path | Body | Answer |
| --- | --- | --- | --- |
| GET | `/api/rules` | none | `Rules` |
| PUT | `/api/rules` | `{aloneUpToCents, approvalUpToCents, substitutes, maxExtraPct, perWeekCents?, code}` | `Rules`, one new pass version, one ledger entry |

* `code`: the account's 6 digit approval code (also accepted as `X-Approve-Code`). 403 wrong code, 429
  after five wrong codes.
* 422 when `aloneUpToCents > approvalUpToCents`, `perWeekCents < approvalUpToCents`, or a value is below 0
  or above 100,000.00 €.
* Without a connected agent the Rules are saved and signed into the pass the next agent will get.

## Settings

```
Settings = {
  kitchen: {name: string, customerNumber: string, deliveryAddress: string},
  diet: ("FREE_FROM_LACTOSE" | "FREE_FROM_GLUTEN" | "VEGAN")[],
  login: {email: string | null}
}
```

| Method | Path | Body | Answer |
| --- | --- | --- | --- |
| GET | `/api/settings` | none | `Settings` |
| PUT | `/api/settings/kitchen` | `{name, deliveryAddress}` | `Settings` (no code) |
| PUT | `/api/settings/diet` | `{diet, code}` | `Settings`, one new pass version, one ledger entry |
| PUT | `/api/settings/login` | `{currentPassword, email?, password?}` | `Settings`; 403 wrong current password; not on demo copies |
| PUT | `/api/settings/approval-code` | `{current, next}` | 204; 403 wrong current code; 403 on demo copies (they keep 246810) |

Valio's answers are recorded for lactose free only, so the other diets save and sign but most requests
then find nothing.

## Demo (demo copies only, 404 elsewhere)

| Method | Path | Body | Answer |
| --- | --- | --- | --- |
| POST | `/api/demo/example` | none | `AskOut` (today's shape): the connected demo agent sends "1000 litres of lactose-free milk by Monday, budget 1200 euro" |
| POST | `/api/demo/ask` | `{text}` | `AskOut`, as today, through this account's agent |
| POST | `/api/demo/stock-out` | `{on}` | `DemoState`, as today |
| POST | `/api/demo/reset` | none | `DemoState`; this copy goes back to the filled demo kitchen |

`/api/demo/example` answers 409 "connect the demo agent first" when no demo agent is active, and the
agent's own refusal (in `lines` and `final`) when it is paused.

## Approvals

`POST /api/orders/{id}/approve` and `/reject` and the Steady Order buttons stay as they are, but check
the account's own code (demo copies: 246810). `GET /api/demo` keeps `codeRequired: true`.

## Accessor

How backend code gets the current account's store (code in `src/backend/validio/api/accounts.py` and
`api/state.py`).

* **Web routes:** take `ctx: CtxDep` from `api/ui.py` (`Depends(request_ctx)`). `request_ctx(request)`
  resolves the `validio_session` cookie to the account's `Ctx`; without a session it is `get_ctx()`, the
  local kitchen, which the gate only lets callers on this machine reach. The Steady Order routes call
  `steady._ctx(request)` the same way.
* **A Ctx:** `ctx.rt` is the account's `Runtime` (own `validio.db`, `keys/`, `RLock`); `ctx.db_path`,
  `ctx.keys_dir`, `ctx.store`, `ctx.audit`, `ctx.orders`, `ctx.nonces`, `ctx.code_tries` are all per
  account. Catalog and Valio client are shared. `ctx.account` is the account row (dict: `id`, `name`,
  `email`, `customer`, `address`, `is_demo`, `rules_saved`, `created_at`, ...) or `None` for the local
  kitchen. `ctx.code_ok(code)` checks the account's approval code (scrypt hash; the env code for the local
  kitchen), `ctx.has_code` says whether one is set. `ctx.reset()` copies the template again for an account.
* **By id, no request:** `get_accounts().ctx(account_id)` (LRU of 64 open accounts). Use this for
  `/agent/v1/k/{account}` and `/mcp/k/{account}/`. `get_accounts().get(id)` / `.update(id, **cols)` read
  and write the account row (add columns in `SCHEMA`; `create table if not exists` will not add them to an
  existing db, so add an `alter table` guard when you add one).
* **Code without a request** (MCP tools, the in-process demo agent): `get_ctx()` returns the Ctx in the
  contextvar `state.current` when set, else the local kitchen. `/api/demo/ask` sets it around its
  `asyncio.run`, so the MCP tools in that run work on the account. The streamable-HTTP MCP sessions do
  not inherit a contextvar from middleware: read the account from the path there.
* **Template:** `make template` plays the five scenes once into `data/template/` (validio.db plus keys).
  New accounts copy it (sqlite backup plus keys, milliseconds); without it they get a plain `seed.reset`.
  All copies share the template's kitchen key. Env: `VALIDIO_ACCOUNTS` (default `data/accounts`),
  `VALIDIO_TEMPLATE` (default `data/template`).
* **Tests:** set `VALIDIO_ACCOUNTS` and `VALIDIO_TEMPLATE` to a tmp dir; `get_accounts()` makes a new
  registry when they change. See `tests/test_accounts.py`.
* Until the agent connection lands, `GET /api/account` answers `agent: {state: "none", versions: []}` and
  `setup.agent` is true only on demo copies (`accounts.agent_state` is the hook to replace).
