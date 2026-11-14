# Plan: one account per kitchen

Plan of Saturday 14 November, 14:20. It is built and live. The pages named below (Inbox, Orders, Ledger) were later replaced by Home, Activity, Rules, Agent and Settings; [../README.md](../README.md) describes the current state.

## Why

Today Validio is one shared demo page: the limits sit inside the Spend Pass page and writes need a demo token. A real kitchen needs its own account with its own data, one place for settings and a way to connect its agent.

## Three parties

* **Kitchen:** the only party with a UI. Every kitchen has its own account.
* **Validio:** in the middle. Checks every agent request, orders alone, asks the kitchen or blocks, writes the ledger.
* **Valio Aimo:** behind Validio, API only. No accounts in our app; the kitchen's customer number is a field in its account.

The kitchen connects its purchasing agent to its account.

## Screens

* **Login:** "Try the demo kitchen" (each browser gets its own fresh copy, so jurors never click in each other's data), email login, create account.
* **Sidebar:** Inbox, Orders, Agent, Ledger. At the bottom the kitchen's name, it opens Settings. On the phone the kitchen name sits top left.
* **Inbox:** what waits for you. Setup checklist until done: Kitchen, Rules, Connect agent. Requests come only from the connected agent.
* **Orders:** requests and steady orders in one list.
* **Agent:**
  * Connect with a pairing code, then a consent screen (Allow / Deny). The consent screen shows a verification code the agent shows too.
  * **Rules**, the one place for what the agent may do: orders alone up to X €, needs approval up to Y €, blocked above; per week; substitutes. One save, one approval code, a new signed pass version.
  * Pause, Disconnect, link to its ledger entries, technical details folded away.
* **Ledger:** as today, plus pass replaced, connected, paused, disconnected.
* **Settings**, one page: Kitchen, Diet and allergens, Login and approval code, Theme, Log out.
* **Demo bar** on demo kitchens only: approval code and Reset.

Cut for now: notifications, presets, several users per kitchen, real OAuth.

## Demo order

1. Try the demo kitchen.
2. Connect a real agent (MCP connector URL), check the verification code, Allow.
3. The agent sends the example request (1,000 l lactose-free milk): ordered alone.
4. Lower the limit in Rules, the agent asks again: now it waits. Approve with the code.
5. Pause the agent: its next request is refused and logged.

## What stays

Matching, Valio lookups, fact grades, Cedar rules, ledger chain, steady orders, phone approval, MCP and OpenAPI for agents.

## Open

* Gemini API key from the Google event account, so the agent runs on a real model.
