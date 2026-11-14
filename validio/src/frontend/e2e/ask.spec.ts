import { test, expect } from "@playwright/test";
import { askLog, askRow, notRecorded, shortReason } from "../src/lib/ask";
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
  expect(askRow(r, item).sub).toBe("Over the 100.00 € budget");
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

test("short reasons: at most about five words", () => {
  expect(shortReason("Asks you: 160.30 € is over the budget of 100.00 € the request names.")).toBe("Over the 100.00 € budget");
  expect(shortReason("160.30 € is over the budget of 1,100.00 € the request names.")).toBe("Over the 1,100.00 € budget");
  // Anything else passes through.
  expect(shortReason("Out of stock (simulated). The swap needs you.")).toBe("Out of stock (simulated). The swap needs you.");
});

// The raw lines of one ask, as the backend sends them (shortened where it lists options).
const CREAM = [
  "kitchen  100 litres of whipping cream by Monday\n",
  'agent -> request_supply  lines=[{"text": "100 litres of whipping cream by Monday"}], deliverBy="2026-11-16"',
  "Validio <- request_supply\n  request R-1: working, checked 7 products live in 4 calls\n    line 1: 100 litres of whipping cream by Monday\n      chosen          465193 Lactose-free cream 58 × 1.75 l  338.14 €\n    decision: auto_order (auto-order) May order it alone: 338.14 € is inside the auto limit of 1,200.00 €.\n",
  'agent -> confirm_order  requestId="R-1", choice=[{"productId": "465193", "salesQty": 58}]',
  "Validio <- confirm_order\n  order O-1: placed, 338.14 €\n    58 × 1.75 l of 465193 Lactose-free cream\n",
  'agent -> get_order  orderId="O-1"',
  "Validio <- get_order\n  order O-1: placed, 338.14 €\n    58 × 1.75 l of 465193 Lactose-free cream\n",
  "\nagent  Order O-1 is placed.\n",
];
const QUARK = [
  "kitchen  50 kg of quark by Monday, budget 100 euro\n",
  'agent -> request_supply  lines=[{"text": "50 kg of quark by Monday, budget 100 euro"}], deliverBy="2026-11-16"',
  "Validio <- request_supply\n  request R-2: waiting, checked 12 products live in 6 calls\n    line 1: x\n    decision: ask_human (over-budget) Needs a person: 160.30 € is over the budget of 100.00 € the request names.\n",
  'agent -> get_order  orderId="O-2"',
  "Validio <- get_order\n  order O-2: waiting, 160.30 €\n",
  "\nagent  Order O-2 waits for the owner's approval on the phone.\n",
];
const PARMESAN = [
  "kitchen  20 kg of parmesan by Monday\n",
  'agent -> request_supply  lines=[{"text": "20 kg of parmesan by Monday"}], deliverBy="2026-11-16"',
  "Validio <- request_supply\n  request R-3: blocked, checked 0 products live in 0 calls\n    line 1: 20 kg of parmesan by Monday\n    decision: block () Valio has no lactose-free parmesan. Nothing was ordered.\n",
  "\nagent  Validio blocked request R-3, nothing ordered. Valio has no lactose-free parmesan. Nothing was ordered.\n",
];
const YOGHURT = [
  "kitchen  30 litres of yoghurt by Monday\n",
  'agent -> request_supply  lines=[{"text": "30 litres of yoghurt by Monday"}], deliverBy="2026-11-16"',
  "Validio <- request_supply\n  error: Error executing tool request_supply: 503 not recorded: Valio's answers for yoghurt aren't recorded for this demo. Nothing was ordered.\n",
  // The agent repeats what Validio said; the log says it once.
  "\nagent  Valio's answers for yoghurt aren't recorded for this demo. Nothing was ordered.\n",
];
const flat = (steps: { who: string; what: string }[]) => steps.map((x) => `${x.who}: ${x.what}`);

test("the log: plain steps, who and what, no code names, no repeats", () => {
  expect(flat(askLog(CREAM))).toEqual([
    "Kitchen: 100 litres of whipping cream by Monday",
    "Agent: Asks Validio",
    "Validio: Checked 7 products live. R-1 may be ordered alone.",
    "Agent: Confirms R-1",
    "Validio: Placed O-1, 338.14 €",
    "Agent: Checks O-1",
    "Agent: Order O-1 is placed.",
  ]);
  expect(flat(askLog(QUARK))).toEqual([
    "Kitchen: 50 kg of quark by Monday, budget 100 euro",
    "Agent: Asks Validio",
    "Validio: Checked 12 products live. R-2 needs you.",
    "Agent: Checks O-2",
    "Validio: O-2 waits for you, 160.30 €",
    "Agent: Order O-2 waits for the owner's approval on the phone.",
  ]);
  expect(flat(askLog(PARMESAN))).toEqual([
    "Kitchen: 20 kg of parmesan by Monday",
    "Agent: Asks Validio",
    "Validio: Blocked R-3.",
    "Agent: Validio blocked request R-3, nothing ordered.",
  ]);
  expect(flat(askLog(YOGHURT))).toEqual([
    "Kitchen: 30 litres of yoghurt by Monday",
    "Agent: Asks Validio",
    "Validio: Valio's answers for yoghurt aren't recorded for this demo.",
  ]);
  for (const l of [CREAM, QUARK, PARMESAN, YOGHURT].flatMap((x) => flat(askLog(x)))) expect(l).not.toMatch(/[{}[\]"_→←]|\b\d{6}\b|request_supply|confirm_order|get_order/);
});
