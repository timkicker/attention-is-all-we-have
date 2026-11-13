// The fixture as a small stateful backend. State lives in localStorage so the
// phone tab and the desktop tab see the same approval, the way they will once
// both talk to the real server. Every read and write is guarded: a browser
// that refuses storage just keeps the state in memory.

import {
  MILK_REQUEST,
  MILK_SENTENCE,
  MOZZARELLA_REQUEST,
  SPEND_PASS,
  STEADY_ID,
  STEADY_PENDING,
  STEADY_RENEWED,
} from "./fixture";
import type {
  DemoState,
  InboxItem,
  Ledger,
  LedgerEntry,
  Order,
  SpendPass,
  SteadyOrder,
  SteadyOrderSummary,
  SupplyRequest,
} from "./types";

interface MockState {
  stockOut: boolean;
  approval: "none" | "approved" | "rejected";
  renewed: boolean;
  accepted: string[];
}

const KEY = "validio-mock-v1";
const START: MockState = { stockOut: false, approval: "none", renewed: false, accepted: [] };
let memory: MockState = { ...START };

function load(): MockState {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) memory = { ...START, ...JSON.parse(raw) };
  } catch {
    // storage unavailable, keep memory
  }
  return memory;
}

function save(next: MockState): void {
  memory = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage unavailable, keep memory
  }
}

export function resetMock(): void {
  save({ ...START, accepted: [] });
}

const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v));

function mozzarella(s: MockState): SupplyRequest {
  const r = clone(MOZZARELLA_REQUEST);
  if (s.approval === "approved") {
    r.status = "ordered";
    r.decision = {
      outcome: "ask_human",
      ruleIds: ["ask-human"],
      sentence:
        "Ordered 10 bags of 463383 Maestrella grated mozzarella lactose free 2.5 kg for 196.60 € after the owner approved. Valio was asked again before placing it.",
    };
  } else if (s.approval === "rejected") {
    r.status = "rejected";
    r.decision = {
      outcome: "ask_human",
      ruleIds: ["ask-human"],
      sentence: "The owner rejected the swap. Nothing was ordered for this line.",
    };
  }
  return r;
}

function requests(s: MockState): SupplyRequest[] {
  const list = [clone(MILK_REQUEST)];
  if (s.stockOut) list.push(mozzarella(s));
  return list;
}

export async function inbox(): Promise<InboxItem[]> {
  const s = load();
  return requests(s)
    .map((r) => ({
      id: r.id,
      createdAt: r.createdAt,
      text: r.text,
      status: r.status,
      sentence: r.status === "waiting" && r.question ? r.question : r.decision.sentence,
      totalCents: r.totalCents,
    }))
    .reverse();
}

export async function request(id: string): Promise<SupplyRequest> {
  const r = requests(load()).find((x) => x.id === id);
  if (!r) throw new Error(`No request with id ${id}.`);
  return r;
}

export async function spendPass(_id: string): Promise<SpendPass> {
  return clone(SPEND_PASS);
}

export async function order(id: string): Promise<Order> {
  const s = load();
  if (id === "O-1") {
    return {
      id,
      requestId: "R-1",
      state: "placed",
      lines: [{ productId: "464306", name: "Valio Arki Eila 1 l", quantity: 1000, unit: "cartons", totalCents: 101000 }],
      totalCents: 101000,
      history: [{ state: "placed", at: "2026-11-14T10:00:06+02:00" }],
    };
  }
  if (id === "O-2" && s.stockOut) {
    const history: Order["history"] = [{ state: "waiting", at: "2026-11-14T10:00:47+02:00" }];
    if (s.approval === "approved") {
      history.push({ state: "approved", at: "2026-11-14T10:01:05+02:00" });
      history.push({ state: "placed", at: "2026-11-14T10:01:06+02:00" });
    } else if (s.approval === "rejected") {
      history.push({ state: "rejected", at: "2026-11-14T10:01:05+02:00" });
    }
    return {
      id,
      requestId: "R-2",
      state: history[history.length - 1].state,
      lines: [{ productId: "463383", name: "Maestrella grated mozzarella lactose free 2.5 kg", quantity: 10, unit: "bags", totalCents: 19660 }],
      totalCents: 19660,
      history,
    };
  }
  throw new Error(`No order with id ${id}.`);
}

export async function approve(orderId: string): Promise<Order> {
  const s = load();
  if (orderId !== "O-2" || !s.stockOut) throw new Error(`No order with id ${orderId}.`);
  if (s.approval !== "none") throw new Error("This order was already answered.");
  save({ ...s, approval: "approved" });
  return order(orderId);
}

export async function reject(orderId: string): Promise<Order> {
  const s = load();
  if (orderId !== "O-2" || !s.stockOut) throw new Error(`No order with id ${orderId}.`);
  if (s.approval !== "none") throw new Error("This order was already answered.");
  save({ ...s, approval: "rejected" });
  return order(orderId);
}

export async function demoState(): Promise<DemoState> {
  return { stockOut466375: load().stockOut };
}

export async function stockOut(): Promise<DemoState> {
  const s = load();
  save({ ...s, stockOut: true });
  return { stockOut466375: true };
}

function steady(s: MockState): SteadyOrder {
  const lines = clone(s.renewed ? STEADY_RENEWED : STEADY_PENDING).map((l) =>
    s.accepted.includes(l.productId)
      ? { ...l, result: "accepted" as const, acceptLabel: undefined }
      : l,
  );
  return {
    id: STEADY_ID,
    name: "Weekly Monday order",
    weekday: "Monday",
    guestsPerWeek: 400,
    weeksLearned: 8,
    simulatedHistory: true,
    renewedAt: s.renewed ? "2026-11-14T10:01:15+02:00" : undefined,
    lines,
  };
}

export async function steadyList(): Promise<SteadyOrderSummary[]> {
  const o = steady(load());
  return [
    {
      id: o.id,
      name: o.name,
      weekday: o.weekday,
      lineCount: o.lines.length,
      flagCount: o.lines.filter((l) => l.flags.length > 0 && l.result !== "accepted").length,
      renewedAt: o.renewedAt,
    },
  ];
}

export async function steadyOrder(id: string): Promise<SteadyOrder> {
  if (id !== STEADY_ID) throw new Error(`No Steady Order with id ${id}.`);
  return steady(load());
}

export async function renew(id: string): Promise<SteadyOrder> {
  const s = load();
  save({ ...s, renewed: true });
  return steadyOrder(id);
}

export async function acceptLine(id: string, productId: string): Promise<SteadyOrder> {
  const s = load();
  if (!s.renewed) throw new Error("Renew the order first.");
  if (!s.accepted.includes(productId)) save({ ...s, accepted: [...s.accepted, productId] });
  return steadyOrder(id);
}

// The ledger. Entries are built from the state, then hashed the way the
// blueprint says: SHA-256 over the entry as JSON with sorted keys and no
// spaces, each one carrying the hash before it.

type Draft = Omit<LedgerEntry, "seq" | "prevHash" | "hash">;

function drafts(s: MockState): Draft[] {
  const d: Draft[] = [
    {
      at: "2026-11-14T10:00:02+02:00",
      actor: "agent:buyer-1",
      kind: "request",
      sentence: "The agent asked for 1000 litres of lactose-free milk by Monday.",
      facts: [],
      spendPassId: "M-1",
      disclosed: ["autoLimitCents", "hardCapCents", "diet"],
      ruleIds: [],
    },
    {
      at: "2026-11-14T10:00:05+02:00",
      actor: "validio",
      kind: "decision",
      sentence: MILK_SENTENCE,
      facts: MILK_REQUEST.lines[0].options[0].facts.slice(0, 3),
      spendPassId: "M-1",
      disclosed: ["autoLimitCents"],
      ruleIds: ["auto-order"],
      orderId: "O-1",
    },
    {
      at: "2026-11-14T10:00:05+02:00",
      actor: "validio",
      kind: "decision",
      sentence:
        "Ignored the description of 463047, which talks to AI agents. Descriptions are never used for decisions; its product data lists lactose.",
      facts: MILK_REQUEST.lines[0].options[5].facts,
      spendPassId: "M-1",
      disclosed: ["diet"],
      ruleIds: [],
    },
  ];
  if (s.stockOut) {
    d.push(
      {
        at: "2026-11-14T10:00:45+02:00",
        actor: "presenter",
        kind: "simulation",
        sentence: "Simulated a stock-out of 466375. Valio really has 11,603 bags.",
        facts: [],
        disclosed: [],
        ruleIds: [],
      },
      {
        at: "2026-11-14T10:00:47+02:00",
        actor: "validio",
        kind: "decision",
        sentence:
          "Blocked 466151, 468526 and 475908 from Valio's substitute list because they contain lactose. 473986 cannot be delivered.",
        facts: [{ field: "Allergen", value: "lactose", grade: "attested", source: "catalog:allergens" }],
        spendPassId: "M-1",
        disclosed: ["diet"],
        ruleIds: ["never-break-diet"],
      },
      {
        at: "2026-11-14T10:00:47+02:00",
        actor: "validio",
        kind: "decision",
        sentence: MOZZARELLA_REQUEST.decision.sentence,
        facts: MOZZARELLA_REQUEST.lines[0].beyondList![0].facts.slice(0, 2),
        spendPassId: "M-1",
        disclosed: ["autoLimitCents", "hardCapCents", "diet"],
        ruleIds: ["ask-human"],
        orderId: "O-2",
      },
    );
    if (s.approval !== "none") {
      d.push({
        at: "2026-11-14T10:01:05+02:00",
        actor: "owner",
        kind: "approval",
        sentence:
          s.approval === "approved"
            ? "The owner approved 10 bags of 463383 for 196.60 € on the phone."
            : "The owner rejected the swap to 463383 on the phone.",
        facts: [],
        spendPassId: "M-1",
        disclosed: [],
        ruleIds: [],
        orderId: "O-2",
      });
    }
    if (s.approval === "approved") {
      d.push({
        at: "2026-11-14T10:01:06+02:00",
        actor: "validio",
        kind: "order",
        sentence: "Asked Valio again: price and stock unchanged. Placed order O-2.",
        facts: [{ field: "Price", value: "196.60 €", grade: "attested", source: "valio:price" }],
        spendPassId: "M-1",
        disclosed: [],
        ruleIds: [],
        orderId: "O-2",
      });
    }
  }
  if (s.renewed) {
    d.push(
      {
        at: "2026-11-14T10:01:15+02:00",
        actor: "validio",
        kind: "renewal",
        sentence:
          "Renewed the weekly Monday order: milk as usual, parmesan split with 40 blocks of 469648 for 18.49 € (2.5 %) more.",
        facts: [],
        spendPassId: "M-1",
        disclosed: ["autoLimitCents"],
        ruleIds: ["auto-order"],
      },
      {
        at: "2026-11-14T10:01:15+02:00",
        actor: "validio",
        kind: "renewal",
        sentence:
          "Held two lines for the chef: pancakes (27 of 30, the only substitute contains wheat) and mozzarella (26 % more per guest).",
        facts: [],
        spendPassId: "M-1",
        disclosed: ["diet"],
        ruleIds: ["ask-human"],
      },
    );
    for (const pid of s.accepted) {
      d.push({
        at: "2026-11-14T10:01:30+02:00",
        actor: "chef",
        kind: "approval",
        sentence:
          pid === "471376"
            ? "The chef ordered 27 cartons of pancakes 471376."
            : "The chef renewed 120 bags of mozzarella 466375 despite the flag.",
        facts: [],
        spendPassId: "M-1",
        disclosed: [],
        ruleIds: [],
      });
    }
  }
  return d;
}

function canonical(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canonical).join(",")}]`;
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return `{${Object.keys(o)
      .filter((k) => o[k] !== undefined)
      .sort()
      .map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`)
      .join(",")}}`;
  }
  return JSON.stringify(v);
}

async function sha256(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const ZERO = "0".repeat(64);

export async function ledger(): Promise<Ledger> {
  const entries: LedgerEntry[] = [];
  let prev = ZERO;
  for (const [i, draft] of drafts(load()).entries()) {
    const body = { ...draft, seq: i + 1, prevHash: prev };
    const hash = await sha256(canonical(body));
    entries.push({ ...body, hash });
    prev = hash;
  }
  // Walk the chain again from the start, the same check the server runs.
  let expected = ZERO;
  let brokenAt: number | undefined;
  for (const e of entries) {
    const { hash, ...body } = e;
    if (e.prevHash !== expected || (await sha256(canonical(body))) !== hash) {
      brokenAt = e.seq;
      break;
    }
    expected = hash;
  }
  return { entries, chain: { ok: brokenAt === undefined, count: entries.length, brokenAt } };
}
