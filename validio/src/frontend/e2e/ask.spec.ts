import { test, expect } from "@playwright/test";
import { askLog, askRow, notRecorded } from "../src/lib/ask";
import type { InboxItem, SupplyRequest } from "../src/lib/api/types";

// The ask dialog's row, log and no-request line, as plain functions: no browser needed.
const req = (over: Partial<SupplyRequest>) =>
  ({
    id: "R-1",
    status: "ordered_alone",
    title: "100 litres of lactose-free whipping cream by Mon 16 Nov",
    titleText: "100 litres of lactose-free whipping cream",
    text: "100 litres of whipping cream by Monday",
    moneyText: "338.14 €",
    totalCents: 33814,
    lines: [],
    decision: { outcome: "ordered_alone", ruleIds: [], summary: "Ordered 58 × 1.75 l for 338.14 €." },
    ...over,
  }) as unknown as SupplyRequest;

test("ordered alone: one row, the amount, no sub", () => {
  expect(askRow(req({}))).toEqual({
    id: "R-1",
    status: "ordered_alone",
    title: "100 litres of lactose-free whipping cream",
    end: "338.14 €",
    sub: undefined,
  });
});

test("waiting: the inbox's reason without its lead-in", () => {
  const r = req({ id: "R-2", status: "waiting", titleText: "50 kg of lactose-free quark", moneyText: "160.30 €" });
  const item = { id: "R-2", summary: "Asks you: 160.30 € is over the budget of 100.00 € the request names." } as InboxItem;
  expect(askRow(r, item).sub).toBe("160.30 € is over the budget of 100.00 € the request names.");
});

test("blocked: no amount, the reason once, no doubled prefix", () => {
  const r = req({ id: "R-3", status: "blocked", moneyText: undefined, totalCents: undefined, decision: { outcome: "blocked", ruleIds: [], summary: "Blocked: butter is outside the Spend Pass's product groups." } as never });
  expect(askRow(r)).toMatchObject({ end: undefined, sub: "Butter is outside the Spend Pass's product groups." });
  const p = req({ status: "blocked", moneyText: undefined, decision: { outcome: "blocked", ruleIds: [], summary: "Valio has no lactose-free parmesan." } as never });
  expect(askRow(p).sub).toBe("Valio has no lactose-free parmesan.");
});

test("no request: one short muted line", () => {
  expect(notRecorded("Valio's answers for yoghurt aren't recorded for this demo. Nothing was ordered.")).toBe("Not recorded for this demo: yoghurt");
  expect(notRecorded("Not recorded for this demo: salmon.")).toBe("Not recorded for this demo: salmon");
  expect(notRecorded("Validio could not take the request, nothing ordered. Error 503")).toBe("Validio could not take the request, nothing ordered.");
});

test("the log: one step per line, no JSON, no product ids", () => {
  const lines = [
    "kitchen  100 litres of whipping cream by Monday\n",
    'agent -> request_supply  lines=[{"text": "100 litres of whipping cream by Monday"}], deliverBy="2026-11-16"',
    "Validio <- request_supply\n  request R-1: working, checked 7 products live in 4 calls\n    line 1: 100 litres\n      chosen          465193 Lactose-free cream 58 × 1.75 l  338.14 €\n",
    'agent -> confirm_order  requestId="R-1", choice=[{"productId": "465193", "salesQty": 58}]',
    "Validio <- confirm_order\n  order O-1: placed, 338.14 €\n    58 × 1.75 l of 465193 Lactose-free cream\n",
    "\nagent  Order O-1 is placed.\n",
    'agent -> request_supply  lines=[{"text": "30 litres of yoghurt by Monday"}], deliverBy="2026-11-16"',
    "Validio <- request_supply\n  error: Error executing tool request_supply: 503 not recorded: Valio's answers for yoghurt aren't recorded for this demo. Nothing was ordered.\n",
  ];
  expect(askLog(lines)).toEqual([
    "kitchen  100 litres of whipping cream by Monday",
    "→ request_supply  100 litres of whipping cream by Monday",
    "← R-1 working, checked 7 products live",
    "→ confirm_order  R-1",
    "← O-1 placed, 338.14 €",
    "agent  Order O-1 is placed.",
    "→ request_supply  30 litres of yoghurt by Monday",
    "← Valio's answers for yoghurt aren't recorded for this demo.",
  ]);
  for (const l of askLog(lines)) expect(l).not.toMatch(/[{}[\]"]|\b\d{6}\b/);
});
