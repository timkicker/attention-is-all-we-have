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
  id: string,                 // "k-" and 32 hex digits, also used in the agent URLs below
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
* Signup and new demo copies: at most 10 an hour per client (429), and at most 200 demo copies on disk; the
  oldest copy goes first.
* Login: 401 "wrong email or password" for both cases. Five wrong tries from one client or for one email
  in 15 minutes answer 429.
* Demo: a browser that already holds a demo session gets the same copy back (reload keeps the state). A
  new browser gets a fresh copy of the filled demo kitchen: the five scenes played, rules saved, no
  agent connected yet (the person connects a real agent over MCP or the pairing code, then Allow). Copies older than 48 h
  are deleted.
* Phone link: a one-time link, valid 10 minutes, that logs the phone into the same account and opens
  `path`. The web app turns `url` into a QR code or a copy button.

## Agent

```
AgentState = {
  state: "none" | "pairing" | "consent" | "active" | "paused",
  pairing?: {code: string, expiresAt: string, mcpUrl: string, apiUrl: string},   // state "pairing"
  consent?: {name: string, keyId: string, may: string[], verifyCode: string, at: string | null}, // "consent"
  agent?: {name: string, kind: "agent" | "mcp", keyId: string, connectedAt: string,
           lastUsedAt: string | null, passId: string, passVersion: number},        // "active" / "paused"
  versions: [{version: number, at: string, why: string}]                           // newest first
}
```

* `code`: 8 characters, letters and digits without look-alikes (`7KQ4-M2XD` shown with a dash, sent
  either way), valid 10 minutes.
* `mcpUrl`: `https://<host>/mcp/c/<token>/`, the connector for any MCP agent (see below);
  `apiUrl`: `https://<host>/agent/v1/k/<accountId>`. Signing agents (the CLI) keep using the code and
  `/mcp/k/<accountId>/`.
* `may`: the Rules in words, e.g. `["Order alone up to 1,200.00 €", "Ask you up to 2,000.00 €",
  "Never above 2,000.00 €", "Substitutes from Valio's list"]`.
* `keyId`: the JWK thumbprint of the agent's key, first 8 characters, for the Technical fold.
* `verifyCode`: `XXX-XXX` from `A-Z` and `2-9` without `0 O 1 I L`, new for every connection, made when
  the pairing turns into consent (the first request on the connector URL, or a signing agent's
  `POST /agent/v1/.../pair`, which gets it back as `verifyCode`). While consent waits, every tool call on
  `/mcp/c/<token>/` answers an error that starts "Waiting for the kitchen to press Allow in Validio. Show
  the user this verification code: <CODE>. It must match the code on the Validio Agent page." The person
  presses Allow only when the agent shows the same code. Cleared on allow, deny, cancel and disconnect.
* `consent.at`: when the agent's first call came (the call that made the consent), on the kitchen's
  clock. `null` only for a consent stored before the field existed.
* `versions[].why`: "Agent connected", "Rules changed", "Diet changed", "Agent disconnected".

| Method | Path | Body | Answer |
| --- | --- | --- | --- |
| GET | `/api/agent` | none | `AgentState` |
| POST | `/api/agent/pair` | none | `AgentState` in `pairing` (a new code each time) |
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

### Any MCP agent: the connector URL

Many MCP agents (chat apps with custom connectors, coding tools, own scripts) speak MCP over streamable HTTP
but cannot sign a key binding. The pairing screen serves them too, with no extra step:

* `POST /api/agent/pair` also makes a fresh P-256 agent key that Validio holds for this kitchen, and a
  connector token (32 random bytes, urlsafe). `pairing.mcpUrl` is `https://<host>/mcp/c/<token>/`. The token
  is kept in clear only while pairing waits (so a reload still shows the URL); from Allow on only its SHA-256
  is kept.
* The first MCP request on that URL while pairing waits moves the kitchen to `consent` with a fresh
  `consent.verifyCode` and `consent.name` the name the MCP client gives: `clientInfo.title`, else
  `clientInfo.name`, of its `initialize` (or, in the 2026 protocol, the `io.modelcontextprotocol/clientInfo`
  stamp in `_meta` of `server/discover` and every request after it). The name is cut to one printable line
  of at most 60 characters; `claude-code` reads "Claude Code". Without a usable name (none, empty, or one the
  screens use for someone else: You, Validio, Demo) it is "MCP agent", and a later request on the same URL
  that brings a name renames that consent once. After Allow the name stays. Until Allow every tool answers an error that
  starts "Waiting for the kitchen to press Allow in Validio. Show the user this verification code: <CODE>. It
  must match the code on the Validio Agent page."
* Allow signs M-1 again to the held key (version +1, ledger entry "Connected Claude Code..."); `agent.kind` is
  `"mcp"` (`"agent"` for an agent with its own key, which pairs with the code as before).
* From then on `/mcp/c/<token>/` offers the same MCP tools as `/mcp/k/<account>/`, without `spendPass`;
  `idempotencyKey` is optional. Validio presents the pass with the held key and a fresh nonce on every call,
  and makes a random idempotency key when none is sent (each call is a new request). Rules, approval, Pause
  (401 with one ledger entry) are unchanged. `agent.name`, the ledger's `actorText` of the agent's entries,
  Home's `agent.name` and Activity's `asked.agentName` all show that name (actor `agent:claude-code`).
* Only the code expires after 10 minutes; the URL stays valid until Cancel, Deny, Disconnect, a new pairing
  or another agent allowed with the code, or until nobody used it for 30 days (one ledger entry, the agent
  is disconnected). Then `/mcp/c/<token>/` answers 404, as does an unknown token. The URL is a bearer
  secret: whoever holds it orders as the kitchen's agent within the Rules, and the verification code only
  tells the person which connection waits, not who holds the URL. Access logs show it as `/mcp/c/***/`.
  The host allowlist (`VALIDIO_MCP_HOSTS`, DNS rebinding protection) is the same as for `/mcp/k/`.
* Use: add the URL as a remote MCP server (streamable HTTP, no OAuth) in the agent's settings, for example
  a custom connector in a chat app or `<tool> mcp add --transport http validio <URL>` in a coding tool.

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
Account ids carry 128 random bits (`k-` and 32 hex digits). On `/agent/v1/k/...` and `/mcp/k/...` the reads
`get_request` and `get_order` need the pass too (header, or the `spendPass` argument over MCP), and every
pass must be the very copy this kitchen signed last, so a pass from another demo copy (same template key)
gets a 401.

## Rules

What the agent may do, in one place. Alone and approval always count per order. With `perWeekCents` set,
the week counts every order placed under the pass together (over it: blocked); null means no weekly limit.

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
  passVersion: number,
  diet: {
    mustBe: string[],            // every line must be all of these: "lactose-free", "gluten-free", "vegan"
    never: string[],             // no line may contain any of these allergens: "nuts", "milk", ...
    options: {mustBe: string[], never: string[]}   // every word the two lists take
  }
}
```

| Method | Path | Body | Answer |
| --- | --- | --- | --- |
| GET | `/api/rules` | none | `Rules` |
| PUT | `/api/rules` | `{aloneUpToCents, approvalUpToCents, substitutes, maxExtraPct, perWeekCents?, diet?: {mustBe, never}, code}` | `Rules`, one new pass version, one ledger entry |

* `code`: the account's 6 digit approval code (also accepted as `X-Approve-Code`). 403 wrong code, 429
  after five wrong codes within 15 minutes, for 15 minutes.
* 422 when `aloneUpToCents > approvalUpToCents`, `perWeekCents < approvalUpToCents`, or a value is below 0
  or above 100,000.00 €.
* Without a connected agent the Rules are saved and signed into the pass the next agent will get.
* `diet` left out keeps the diet as it is. A word not in `options` is a 422 and changes nothing.
* `mustBe` is the pass's `diet` claim (`FREE_FROM_LACTOSE` and so on, as `/api/settings/diet` sets it).
  `never` is the plain claim `neverContains`; each word stands for the GS1 allergen codes Valio sends
  (`policy/mandate.NEVER_ALLERGENS`, "nuts" is tree nuts and every single nut). Cedar keeps it through the
  diet inputs (docs/RULES.md): a product Valio lists as containing one is blocked, one that may contain one or
  has no allergen data waits for a person. The Steady Order has its own pass and does not carry it.

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
| PUT | `/api/settings/diet` | `{diet, code}` | `Settings`, one new pass version, one ledger entry (kept as an alias; `/api/rules` takes the diet too) |
| PUT | `/api/settings/login` | `{currentPassword, email?, password?}` | `Settings`; 403 wrong current password; not on demo copies |
| PUT | `/api/settings/approval-code` | `{current, next}` | 204; 403 wrong current code; 403 on demo copies (they keep 246810) |

Valio's answers are recorded for lactose free only, so the other diets save and sign but most requests
then find nothing.

## Home and Activity

Composed from requests, orders, the Steady Order and the ledger (`api/activity.py`); nothing new is stored.
Money in cents, times ISO-8601 with the offset.

```
ActivityItem = {
  id: string,                    // "R-4" for a request, "S-1" for the Steady Order
  kind: "request" | "standing",
  status: "ordered" | "waiting" | "blocked" | "standing",
  title: string,                 // "1,500 litres of lactose-free milk", from the parsed need
  why: string,                   // one line in the Rules' words, no full stop
  totalCents: number | null,
  at: string,
  orderId: string | null,
  approvedByYou: boolean         // ordered because the owner approved it, not alone
}
```

* Status: ordered alone and approved are `ordered` (`approvedByYou` tells them apart); waiting is `waiting`; blocked and rejected are
  `blocked`. A request cleared to order alone that the agent has not confirmed yet is no item until it is.
* `why`: "Under your 1,200.00 € limit, ordered alone", "Over your 1,200.00 € limit for ordering alone",
  "Above your 5,000.00 € limit, blocked", "You approved it", "You said no"; the Steady Order "Every Monday,
  4 lines" (", 1 waiting for you" for lines that wait for the owner after a renewal, ", 1 blocked" for lines
  blocked this week); its `totalCents` is what the ordered lines cost, null before a renewal.
* Newest first by `at` (a request's time; the Steady Order's renewal, else its last ledger entry, else the
  start of its pass).

| Method | Path | Answer |
| --- | --- | --- |
| GET | `/api/home` | `{agent: {state, name, lastUsedAt}, week: {usedCents, capCents}, setup: {rulesSaved, agentConnected, firstOrder}, needsYou: ActivityItem[], latest: ActivityItem[]}` |
| GET | `/api/activity?status=all\|ordered\|waiting\|blocked\|standing` | `{items: ActivityItem[], counts: {all, ordered, waiting, blocked, standing}}`; 422 for another status |
| GET | `/api/activity/{id}` | `ActivityDetail`; 404 for an unknown id |

* Home: `agent.name` is the connected agent's name, or the waiting one's during consent. `week.usedCents` is
  what placed orders under M-1 add up to, `capCents` the Rules' per week limit. `needsYou` holds the waiting
  items, `latest` the newest five of all. `firstOrder` is true once a request was ordered.
* `counts` count every item whatever the filter.

```
ActivityDetail = {
  item: ActivityItem,
  asked: {text: string, agentName: string},   // the agent's own words; its name (Steady Order: "Validio")
  checks: {label: "Product" | "Price" | "Stock" | "Allergens" | "Substitute", value: string,
           note: string | null, ok: boolean | null}[],   // per chosen product; ok null: not confirmed either way
  rule: {text: string, version: number},       // the rule that decided; the pass version in force then
  result: {orderId: string, orderIds: string[], delivery: string | null} | null,   // what was placed: one
                                               // order, or the Steady Order's orders this week (orderId the first)
  approval: {orderId: string, holdUntil: string} | null,        // only while waiting
  proof: {at: string, actor: string, text: string, hash: string}[]   // the ledger entries of this item
}
```

* `approval.holdUntil` is Valio's earliest order cut-off for the chosen products, else the end of the pass.
  Approve and reject stay `POST /api/orders/{orderId}/approve` (with the code) and `/reject`.
* `proof.actor` is "You", "Validio" or the agent's name; `text` the ledger's `displayText`; `hash` the
  entry's hash in the chain (`/api/ledger`).

## Demo (demo copies only, 404 elsewhere)

| Method | Path | Body | Answer |
| --- | --- | --- | --- |
| POST | `/api/demo/reset` | none | `DemoState`; this copy goes back to the filled demo kitchen |

There is no shortcut that orders or changes stock: requests come only from an agent over MCP or the
agent API. The scene 3 stock-out is set by the template build (`scripts/demo_check.py`) in the store.

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
* **Keys:** every account, demo copies too, gets its own kitchen key, agent key and issuer
  (`kitchen:<account id>`) when it is made or reset (`seed.rekey`): its passes are signed again by the new key
  and so is the ledger head. No account shares a signing key with the template or with another account.
  Accounts made before this change keep the template's shared demo keys until their next reset: nothing
  rekeys them on open (left as is on purpose, a reset or a new account gets its own).
* **Clock and pass window:** a kitchen's own account (`is_demo` false) decides on the wall clock
  (`Runtime(real_clock=True)`). Its Spend Pass M-1 names no fixed delivery day and is valid for 30 days from
  each signing; `Accounts.ctx` signs it again, with one ledger entry, once fewer than seven days are left
  (`settings.renew_window`). Demo copies and the local kitchen keep the demo clock and the demo window.
* **By id, no request:** `get_accounts().ctx(account_id)` (LRU of 64 open accounts). Use this for
  `/agent/v1/k/{account}` and `/mcp/k/{account}/`. `get_accounts().get(id)` / `.update(id, **cols)` read
  and write the account row (add columns in `SCHEMA`; `create table if not exists` will not add them to an
  existing db, so add an `alter table` guard when you add one).
* **Code without a request** (MCP tools, an in-process MCP client in tests): `get_ctx()` returns the Ctx in
  the contextvar `state.current` when set, else the local kitchen. An in-process client sets it around its
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
