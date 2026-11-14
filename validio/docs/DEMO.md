# Demo click-through

The click path takes about two minutes. Open https://timkicker--validio.us-east.modal.run, or `make demo` on http://127.0.0.1:8410, in a browser at 1280 px. Keep a second window at 390 px for the phone. The steps follow `src/frontend/e2e-live/flow.demo.ts`, which runs the same path in a browser with a real MCP client (`make e2e-live`, or with `E2E_BASE=<url>` against the live site).

## 1 Try the demo kitchen

The login page offers email login, **Create account** and **Try the demo kitchen**. Click **Try the demo kitchen**. Each browser gets its own copy of the filled demo kitchen, so two people never click in each other's data. A reload lands in the same copy.

A thin bar on top shows the approval code 246810 and **Reset**. The code is shown on purpose, because there is no other way to learn it. The sidebar holds Home, Activity, Rules and Agent, and the kitchen's name at the bottom opens Settings. On the phone the kitchen's name sits at the top.

**Activity** already holds the demo scenes: the lactose-free milk ordered alone, the mozzarella swap the owner approved, and the weekly Steady Order. **Rules** shows the demo kitchen's limits: ordered alone up to 1,200.00 €, waiting for you up to 2,000.00 €, 8,000.00 € per week, and substitutes from Valio's list with up to 5 % extra cost.

## 2 Connect an agent

Click **Agent**, then **Connect agent**. The page shows an MCP address `…/mcp/c/<token>/`. Add it to any MCP client as a remote server, for example `claude mcp add --transport http validio <URL>` in the Claude Code CLI.

The agent's first call turns the Agent page into a check. It shows a verification code like `K7P-3QX` and lists what the agent may do. The agent receives the same code: every tool answers "Waiting for the kitchen to press Allow in Validio. Show the user this verification code: …" until you press Allow, and `connection_status` returns the code at any time. If the codes match, click **Allow**. The page now shows the agent's name, when it connected and when it was last used.

## 3 Order alone

Ask the agent: "1000 litres of lactose-free milk by Monday, budget 1200 euro". It calls `request_supply`, gets `auto_order` and confirms. **Home** shows the order under Latest as "Ordered alone". Open it in **Activity** to see what the agent asked for, what Validio checked at Valio, the rule that decided, and the result. **Proof** at the bottom shows the order's ledger entries with their hashes.

## 4 Lower the limit, then approve

Go to **Rules**, then **Edit**. Set "Ordered alone up to" to 500 and save with the code 246810. Rules now shows the next version.

Ask the agent for the same milk again. This time the answer is `ask_human`, and Home lists the order under **Needs you**. Open it. It says "Waiting for you" and "Not ordered yet". Click **Approve**, type 246810 and confirm. Validio asks Valio again for price and stock before placing the order, and the item disappears from Needs you. This works the same way in the 390 px window.

## 5 Pause and disconnect

On **Agent**, click **Pause**. Ask the agent again. It is refused because the kitchen paused this agent, nothing is ordered, and the refusal is logged. **Disconnect** (confirmed in a dialog) ends the connection, and the MCP address then returns 404.

## 6 Settings and Reset

**Settings** holds the kitchen's name and delivery address, the Valio customer number (read only), login, approval code and theme. Diet and allergens are in Rules.

**Reset** in the demo bar takes the copy back to the filled demo kitchen.

## Things to know

- Valio's answers are recorded for delivery on Mon 16 to Fri 20 Nov 2026 only. Another day returns `503 not recorded` with the recorded days named. "Monday" means 16 Nov.
- Only the products the demo scenes and the common kitchen requests touch are recorded. A different diet in Rules saves and signs, but most requests then find fewer options.
- The scripted recording (`make video`) was written for the first web app and has not been updated to these pages.
- Our own agent (`make agent SCENE=1` to `3`) talks to a running `make demo` on port 8410. Requests it makes go to the single local kitchen, not to a demo copy in the browser. `make demo-check` plays all five scenes on its own server and ends with `ALL SCENES OK`.
