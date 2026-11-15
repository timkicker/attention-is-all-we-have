// The web app without a backend: the v2 contract (UI-V2-API.md) played in this
// browser. The demo kitchen holds the sample day of the wireframes; a kitchen
// made here starts empty. Approving or rejecting R-4 is kept in localStorage,
// so a reload keeps it, as the backend would; Reset goes back to the start.
// Agent and Rules are played in agent.ts, Settings in settings.ts.

import { agentApi } from "./agent";
import { ApiError } from "./error";
import type {
  Account,
  ActivityDetail,
  ActivityFilter,
  ActivityItem,
  ActivityLine,
  ActivityList,
  DemoState,
  HomeOut,
  LoginIn,
  Order,
  SignupIn,
  SupplyRequest,
} from "./types";

// The demo copy's history names its agent the way the server's seed does: the name the demo agent reports
// when it pairs (DEMO_AGENT_NAME in validio/demo/seed.py).
const AGENT = "Kitchen agent";

const copy = <T>(v: T): T => structuredClone(v);

// ---------- the demo kitchen's day ----------

/** Who answered R-4 in this browser. */
type R4 = "waiting" | "approved" | "rejected";
const KEY = "validio-mock-v2-r4";
let r4Memory: R4 = "waiting";

function r4(): R4 {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "approved" || v === "rejected" || v === "waiting") return v;
  } catch {
    // no storage: memory only
  }
  return r4Memory;
}
function setR4(v: R4): void {
  r4Memory = v;
  try {
    localStorage.setItem(KEY, v);
  } catch {
    // see r4()
  }
}

interface Entry {
  item: ActivityItem;
  detail: Omit<ActivityDetail, "item">;
}

const h = (n: number) => `${n.toString(16).padStart(8, "0")}c41e9a07b2d58f3e61a0d4c97b2e5f18a3d6c0b94e7f21a5d8c3b6e09f42a7d1`.slice(0, 64);

const RULE_V = 2;

// The risotto order: an MCP agent asked for 50 portions of butternut squash risotto by product id. Eight lines
// were deliverable by Fri 20 Nov and auto-ordered as O-8; the bouillon was not, and the agent's next request
// ordered a 5 kg one as O-9.
type RisottoLine = [name: string, product: string, qty: string, unitCents: number, n: number, allergens: string, note?: string];
const RISOTTO: RisottoLine[] = [
  ["Butternut squash", "Pumpkin butternutsquash ZA", "10 kg", 149, 10, "Contains no listed allergen"],
  ["Onion", "Onion 1 kg bag Netherlands", "2 × 1 kg", 145, 2, "Contains no listed allergen"],
  ["Garlic", "Garlic peeled China 1 kg", "1 × 1 kg", 895, 1, "Contains no listed allergen"],
  ["Sage", "Sage bunch Italy 100 g", "2 × 100 g", 249, 2, "Contains no listed allergen"],
  ["Pumpkin seeds", "Pumpkin seeds 800 g", "1 × 800 g", 745, 1, "Contains no listed allergen"],
  ["Risotto rice", "Risella risotto rice 5 kg", "1 × 5 kg", 1190, 1, "Contains no listed allergen"],
  ["Salted lactose-free butter", "Lactose-free butter 500 g", "2 × 500 g", 439, 2, "Free from lactose", "Contains milk"],
  ["Grated parmesan reggiano", "Grated parmesan reggiano 1 kg", "1 × 1 kg", 2233, 1, "Contains milk"],
];

function risottoLines(): ActivityLine[] {
  const ordered = RISOTTO.map(([name, product, qty, unit, n, allergens, note], i): ActivityLine => ({
    lineId: `L${i + 1}`,
    name,
    product,
    productId: null,
    qtyText: qty,
    unitPriceCents: unit,
    totalCents: unit * n,
    delivery: "2026-11-20",
    ordered: true,
    reason: null,
    checks: [
      { label: "Product", value: product, note: qty, ok: true },
      { label: "Price", value: `${(unit / 100).toFixed(2)} € per ${qty.includes("×") ? "pack" : "kg"}`, note: "Valio price, until 31 Dec 2026", ok: true },
      { label: "Stock", value: "In stock", note: "Arrives Fri 20 Nov", ok: true },
      { label: "Allergens", value: allergens, note: note ?? null, ok: true },
    ],
    replacedBy: null,
  }));
  return [
    ...ordered,
    {
      lineId: "L9",
      name: "Vegetable bouillon",
      product: "Knorr vegetable bouillon 1 kg",
      productId: null,
      qtyText: "1 × 1 kg",
      unitPriceCents: 1890,
      totalCents: 1890,
      delivery: "2026-11-24",
      ordered: false,
      reason: "Can't be delivered by Fri 20 Nov",
      checks: [
        { label: "Product", value: "Knorr vegetable bouillon powder, low salt 1 kg", note: "1 × 1 kg", ok: true },
        { label: "Price", value: "18.90 € per pack", note: "Valio price", ok: true },
        { label: "Stock", value: "Not before Tue 24 Nov", note: "Asked for Fri 20 Nov", ok: false },
        { label: "Allergens", value: "Contains celery", note: null, ok: true },
      ],
      replacedBy: { requestId: "R-6", orderId: "O-9" },
    },
  ];
}

function risotto(): Entry[] {
  return [
    {
      item: {
        id: "R-6",
        kind: "request",
        status: "ordered",
        title: "1 × 5 kg of vegetable bouillon",
        why: "Under your 1,200.00 € limit, auto-ordered",
        totalCents: 4590,
        at: "2026-11-14T11:44:00+02:00",
        orderId: "O-9",
        approvedByYou: false,
      },
      detail: {
        asked: { text: "Vegetable bouillon for the risotto, 5 kg, delivered by Friday 20 November.", agentName: AGENT },
        checks: [
          { label: "Product", value: "Knorr vegetable bouillon 5 kg", note: "1 × 5 kg", ok: true },
          { label: "Price", value: "45.90 € per pack", note: "Valio price, until 31 Dec 2026", ok: true },
          { label: "Stock", value: "In stock", note: "Arrives Fri 20 Nov", ok: true },
          { label: "Allergens", value: "Contains celery", note: null, ok: true },
        ],
        rule: { text: "Under your 1,200.00 € limit, auto-ordered.", version: RULE_V },
        result: { orderId: "O-9", orderIds: ["O-9"], delivery: "2026-11-20" },
        approval: null,
        proof: [
          { at: "2026-11-14T11:44:01+02:00", actor: AGENT, text: "Asked for 1 × 5 kg of vegetable bouillon", hash: h(61) },
          { at: "2026-11-14T11:44:04+02:00", actor: "Validio", text: "Auto-ordered, order O-9", hash: h(62) },
        ],
      },
    },
    {
      item: {
        id: "R-5",
        kind: "request",
        status: "ordered",
        title: "9 items: butternut squash, onion, garlic and 6 more",
        why: "Under your 1,200.00 € limit, auto-ordered",
        totalCents: 8219,
        at: "2026-11-14T11:40:00+02:00",
        orderId: "O-8",
        approvedByYou: false,
      },
      detail: {
        asked: {
          text: "Ingredients for 50 portions of butternut squash risotto, delivered by Friday 20 November: butternut squash 10 kg, onions 2 × 1 kg, garlic, sage, pumpkin seeds, arborio rice 5 kg, lactose-free butter 2 × 500 g, parmesan 1 kg and Knorr vegetable bouillon 1 kg.",
          agentName: AGENT,
        },
        checks: [],
        rule: { text: "Under your 1,200.00 € limit, auto-ordered.", version: RULE_V },
        result: { orderId: "O-8", orderIds: ["O-8"], delivery: "2026-11-20" },
        approval: null,
        proof: [
          { at: "2026-11-14T11:40:01+02:00", actor: AGENT, text: "Asked for 9 items by Fri 20 Nov: butternut squash, onion, garlic and 6 more", hash: h(51) },
          { at: "2026-11-14T11:40:05+02:00", actor: "Validio", text: "Vegetable bouillon 1 kg can't be delivered by Fri 20 Nov", hash: h(52) },
          { at: "2026-11-14T11:40:06+02:00", actor: "Validio", text: "Auto-ordered 8 items, order O-8", hash: h(53) },
        ],
        lines: risottoLines(),
      },
    },
  ];
}

function day(): Entry[] {
  const answer = r4();
  const r4item: ActivityItem = {
    id: "R-4",
    kind: "request",
    status: answer === "approved" ? "ordered" : answer === "rejected" ? "blocked" : "waiting",
    title: "1,500 litres of lactose-free milk",
    why:
      answer === "approved"
        ? "You approved it"
        : answer === "rejected"
          ? "You said no"
          : "Over your 1,200.00 € auto-order limit",
    totalCents: 151500,
    at: "2026-11-14T11:05:00+02:00",
    orderId: "O-7",
    approvedByYou: answer === "approved",
  };
  const r4proof = [
    { at: "2026-11-14T11:05:02+02:00", actor: AGENT, text: "Asked for 1,500 litres of lactose-free milk", hash: h(41) },
    { at: "2026-11-14T11:05:04+02:00", actor: "Validio", text: "Waiting for you: over 1,200.00 €, under 5,000.00 €", hash: h(42) },
    ...(answer === "waiting"
      ? []
      : [{ at: "2026-11-14T11:20:00+02:00", actor: "You", text: answer === "approved" ? "Approved, order O-7 placed" : "Rejected", hash: h(43) }]),
  ];
  return [
    ...risotto(),
    {
      item: r4item,
      detail: {
        asked: { text: "Order 1,500 litres of lactose-free semi-skimmed milk for Monday.", agentName: AGENT },
        checks: [
          { label: "Product", value: "Valio Eila lactose-free semi-skimmed milk 1 l", note: null, ok: null },
          { label: "Price", value: "1.01 € per litre", note: "Valio price today", ok: true },
          { label: "Stock", value: "In stock, delivery Mon 16 Nov", note: null, ok: true },
          { label: "Allergens", value: "Lactose-free, no nuts", note: null, ok: true },
        ],
        rule:
          answer === "approved"
            ? { text: "Over your 1,200.00 € auto-order limit. You approved it.", version: RULE_V }
            : answer === "rejected"
              ? { text: "You said no.", version: RULE_V }
              : { text: "Over your 1,200.00 € auto-order limit.", version: RULE_V },
        result: answer === "approved" ? { orderId: "O-7", orderIds: ["O-7"], delivery: "2026-11-16" } : null,
        approval: answer === "waiting" ? { orderId: "O-7", holdUntil: "2026-11-14T15:00:00+02:00" } : null,
        proof: r4proof,
      },
    },
    {
      item: {
        id: "R-3",
        kind: "request",
        status: "blocked",
        title: "Hazelnut praline filling 5 kg",
        why: "Contains hazelnut. Your rules say no nuts.",
        totalCents: 21240,
        at: "2026-11-14T10:58:00+02:00",
        orderId: null,
        approvedByYou: false,
      },
      detail: {
        asked: { text: "Order 5 kg of hazelnut praline filling for the dessert menu.", agentName: AGENT },
        checks: [
          { label: "Product", value: "Hazelnut praline filling 5 kg", note: null, ok: null },
          { label: "Price", value: "212.40 €", note: "Valio price today", ok: true },
          { label: "Stock", value: "In stock", note: null, ok: true },
          { label: "Allergens", value: "Contains hazelnut", note: "Your rules say no nuts", ok: false },
        ],
        rule: { text: "Your rules say no nuts, so it is blocked.", version: RULE_V },
        result: null,
        approval: null,
        proof: [
          { at: "2026-11-14T10:58:01+02:00", actor: AGENT, text: "Asked for 5 kg of hazelnut praline filling", hash: h(31) },
          { at: "2026-11-14T10:58:03+02:00", actor: "Validio", text: "Blocked: contains hazelnut", hash: h(32) },
        ],
      },
    },
    {
      item: {
        id: "R-2",
        kind: "request",
        status: "ordered",
        title: "10 × 2.5 kg mozzarella-fontal crumbled cheese",
        why: "Substitute for lactose-free mozzarella 125 g, out of stock",
        totalCents: 18010,
        at: "2026-11-14T10:51:00+02:00",
        orderId: "O-6",
        approvedByYou: false,
      },
      detail: {
        asked: { text: "Order 25 kg of lactose-free mozzarella for Monday.", agentName: AGENT },
        checks: [
          { label: "Product", value: "Lactose-free mozzarella 125 g", note: null, ok: null },
          { label: "Stock", value: "Out of stock", note: "Valio stock today", ok: false },
          { label: "Substitute", value: "Mozzarella-fontal crumbled cheese 2.5 kg", note: "On Valio's substitute list", ok: true },
          { label: "Price", value: "7.20 € per kg", note: "4 % above the original", ok: true },
          { label: "Allergens", value: "Lactose-free, no nuts", note: null, ok: true },
        ],
        rule: { text: "Substitute from Valio's list, under your 1,200.00 € limit, auto-ordered.", version: RULE_V },
        result: { orderId: "O-6", orderIds: ["O-6"], delivery: "2026-11-16" },
        approval: null,
        proof: [
          { at: "2026-11-14T10:51:01+02:00", actor: AGENT, text: "Asked for 25 kg of lactose-free mozzarella", hash: h(21) },
          { at: "2026-11-14T10:51:03+02:00", actor: "Validio", text: "Out of stock, substitute from Valio's list", hash: h(22) },
          { at: "2026-11-14T10:51:05+02:00", actor: "Validio", text: "Auto-ordered, order O-6", hash: h(23) },
        ],
      },
    },
    {
      item: {
        id: "R-1",
        kind: "request",
        status: "ordered",
        title: "1,000 litres of lactose-free milk",
        why: "Under your 1,200.00 € limit",
        totalCents: 101000,
        at: "2026-11-14T10:14:00+02:00",
        orderId: "O-5",
        approvedByYou: false,
      },
      detail: {
        asked: { text: "Order 1,000 litres of lactose-free semi-skimmed milk for Monday.", agentName: AGENT },
        checks: [
          { label: "Product", value: "Valio Eila lactose-free semi-skimmed milk 1 l", note: null, ok: null },
          { label: "Price", value: "1.01 € per litre", note: "Valio price today", ok: true },
          { label: "Stock", value: "In stock, delivery Mon 16 Nov", note: null, ok: true },
          { label: "Allergens", value: "Lactose-free, no nuts", note: null, ok: true },
        ],
        rule: { text: "Under your 1,200.00 € limit, auto-ordered.", version: RULE_V },
        result: { orderId: "O-5", orderIds: ["O-5"], delivery: "2026-11-16" },
        approval: null,
        proof: [
          { at: "2026-11-14T10:14:01+02:00", actor: AGENT, text: "Asked for 1,000 litres of lactose-free milk", hash: h(11) },
          { at: "2026-11-14T10:14:03+02:00", actor: "Validio", text: "Auto-ordered, order O-5", hash: h(12) },
        ],
      },
    },
    {
      item: {
        id: "S-1",
        kind: "standing",
        status: "standing",
        title: "Weekly Monday order, 4 lines",
        why: "Next run Mon 17 Nov, auto-ordered if under your limits",
        totalCents: 198080,
        at: "2026-11-13T09:00:00+02:00",
        orderId: null,
        approvedByYou: false,
      },
      detail: {
        asked: { text: "Every Monday: milk, butter, cream and eggs for the week.", agentName: AGENT },
        checks: [
          { label: "Product", value: "4 lines: milk, butter, cream, eggs", note: null, ok: null },
          { label: "Price", value: "1,980.80 € a week", note: "Valio prices on Thu 13 Nov", ok: true },
          { label: "Allergens", value: "Lactose-free, no nuts", note: null, ok: true },
        ],
        rule: { text: "Each run is checked again; auto-ordered if under your limits.", version: RULE_V },
        result: null,
        approval: null,
        proof: [
          { at: "2026-11-13T09:00:01+02:00", actor: AGENT, text: "Set up the weekly Monday order", hash: h(5) },
          { at: "2026-11-13T09:00:03+02:00", actor: "Validio", text: "Standing order S-1 saved under rules v2", hash: h(6) },
        ],
      },
    },
    {
      item: {
        id: "R-0",
        kind: "request",
        status: "ordered",
        title: "40 kg unsalted butter",
        why: "Under your 1,200.00 € limit",
        totalCents: 38600,
        at: "2026-11-07T14:32:00+02:00",
        orderId: "O-4",
        approvedByYou: false,
      },
      detail: {
        asked: { text: "Order 40 kg of unsalted butter.", agentName: AGENT },
        checks: [
          { label: "Product", value: "Valio unsalted butter 500 g", note: null, ok: null },
          { label: "Price", value: "9.65 € per kg", note: "Valio price on Fri 7 Nov", ok: true },
          { label: "Stock", value: "In stock, delivery Mon 9 Nov", note: null, ok: true },
          { label: "Allergens", value: "Contains milk, no nuts", note: null, ok: true },
        ],
        rule: { text: "Under your 1,200.00 € limit, auto-ordered.", version: RULE_V },
        result: { orderId: "O-4", orderIds: ["O-4"], delivery: "2026-11-09" },
        approval: null,
        proof: [
          { at: "2026-11-07T14:32:01+02:00", actor: AGENT, text: "Asked for 40 kg of unsalted butter", hash: h(1) },
          { at: "2026-11-07T14:32:03+02:00", actor: "Validio", text: "Auto-ordered, order O-4", hash: h(2) },
        ],
      },
    },
  ];
}

/** The demo kitchen has its day; a kitchen made in this browser has nothing yet. */
function entries(): Entry[] {
  const a = read<Account | null>(SESSION, sessionMemory);
  return a?.isDemo ? day() : [];
}

const later = <T>(v: T, ms = 120) => new Promise<T>((r) => setTimeout(() => r(v), ms));

export async function home(): Promise<HomeOut> {
  signedIn();
  const list = entries().map((e) => e.item);
  const [agent, rules] = await Promise.all([agentApi.agent(), agentApi.rules()]);
  // This week: Mon 9 Nov 00:00 Helsinki on, ordered only.
  const usedCents = list
    .filter((i) => i.status === "ordered" && i.at >= "2026-11-09")
    .reduce((n, i) => n + (i.totalCents ?? 0), 0);
  const connected = agent.state === "active" || agent.state === "paused";
  return later({
    agent: {
      state: agent.state,
      name: agent.agent?.name ?? agent.consent?.name ?? null,
      lastUsedAt: agent.agent?.lastUsedAt ?? null,
    },
    week: { usedCents, capCents: rules.perWeekCents },
    setup: { rulesSaved: rules.saved, agentConnected: connected, firstOrder: list.some((i) => i.kind === "request") },
    needsYou: list.filter((i) => i.status === "waiting"),
    latest: list.slice(0, 5),
  });
}

export async function activity(status: ActivityFilter = "all"): Promise<ActivityList> {
  signedIn();
  const list = entries().map((e) => e.item);
  const n = (s: ActivityFilter) => (s === "all" ? list.length : list.filter((i) => i.status === s).length);
  return later({
    items: status === "all" ? list : list.filter((i) => i.status === status),
    counts: { all: n("all"), ordered: n("ordered"), waiting: n("waiting"), blocked: n("blocked"), standing: n("standing") },
  });
}

export async function activityItem(id: string): Promise<ActivityDetail> {
  signedIn();
  const e = entries().find((x) => x.item.id === id);
  if (!e) throw new ApiError(404, `no request ${id}`); // as the backend says it
  return later(copy({ item: e.item, ...e.detail }));
}

/** The fixture plays a server with the approval code set: any 6 digits pass. */
function checkCode(code: string): void {
  if (!/^\d{6}$/.test(code)) throw new ApiError(403, "wrong or missing approval code");
}

function order(id: string): Order {
  const state = r4() === "approved" ? "placed" : r4() === "rejected" ? "rejected" : "waiting";
  return {
    id,
    requestId: "R-4",
    state,
    lines: [],
    totalCents: 151500,
    history: [{ state: "waiting", at: "2026-11-14T11:05:04+02:00" }],
    decision: { outcome: "ask_human", ruleIds: ["approval_up_to"], sentence: "Over your 1,200.00 € auto-order limit" },
    spendPassId: "M-1",
    deliverBy: "2026-11-16",
  };
}

async function decide(id: string, to: R4): Promise<Order> {
  // Only R-4's order O-7 waits for the owner in the demo day.
  if (id !== "O-7" || !entries().length) throw new ApiError(404, `order ${id} not found`);
  if (r4() !== "waiting") throw new ApiError(409, `order ${id} is ${order(id).state}, not waiting`);
  setR4(to);
  return later(order(id));
}

/** The fixture records no option lists (they come from Valio through the backend): nothing to compare. */
export async function request(id: string): Promise<SupplyRequest> {
  throw new ApiError(404, `${id} has no recorded options here`);
}

export async function approve(id: string, code: string): Promise<Order> {
  checkCode(code);
  return decide(id, "approved");
}

export const reject = (id: string): Promise<Order> => decide(id, "rejected");

/** A test sets localStorage "validio-mock-public" to a token: every write then needs it, as on the public link. */
export async function publicGate(token: string): Promise<void> {
  let want: string | null = null;
  try {
    want = localStorage.getItem("validio-mock-public");
  } catch {
    /* no storage, no gate */
  }
  if (want && token !== want) throw new ApiError(401, "wrong or missing kitchen token");
}

export async function reset(): Promise<DemoState> {
  setR4("waiting");
  agentApi.resetMock();
  return { stockOut466375: false, codeRequired: true };
}

// ---------- accounts ----------
// The fixture plays the session cookie with localStorage: who is logged in,
// and the accounts made in this browser. The demo kitchen is the recorded one.

const SESSION = "validio-mock-session";
const ACCOUNTS = "validio-mock-accounts";
const DEMO_CODE = "246810";

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw) return JSON.parse(raw) as T;
  } catch {
    // no storage: nobody stays logged in across a reload
  }
  return fallback;
}

function write(key: string, value: unknown): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // see read()
  }
}

let sessionMemory: Account | null = null;

function signedIn(): Account {
  const a = read<Account | null>(SESSION, sessionMemory);
  if (!a) throw new ApiError(401, "not logged in");
  return a;
}

function enter(a: Account): Account {
  sessionMemory = a;
  write(SESSION, a);
  return copy(a);
}

export async function account(): Promise<Account> {
  return copy(signedIn());
}

/** The demo kitchen as a fresh copy, as POST /api/account/demo answers: rules saved, no agent (agent.ts plays it). */
const DEMO_ACCOUNT: Account = {
  id: "k-demo",
  name: "Hotel Espoo kitchen",
  email: null,
  customerNumber: "hotel-espoo",
  deliveryAddress: "",
  isDemo: true,
  demoCode: DEMO_CODE,
  setup: { kitchen: true, rules: true, agent: false, done: false },
  agent: { state: "none", versions: [] },
  createdAt: "2026-11-14T10:00:00+02:00",
};

export async function demoLogin(): Promise<Account> {
  return enter(copy(DEMO_ACCOUNT));
}

type Stored = Account & { password: string };

export async function login(body: LoginIn): Promise<Account> {
  const found = read<Stored[]>(ACCOUNTS, []).find((a) => (a.email ?? "").toLowerCase() === body.email.trim().toLowerCase());
  if (!found || found.password !== body.password) throw new ApiError(401, "wrong email or password");
  const { password: _, ...a } = found;
  return enter(a);
}

export async function signup(body: SignupIn): Promise<Account> {
  const list = read<Stored[]>(ACCOUNTS, []);
  const email = body.email.trim();
  if (list.some((a) => (a.email ?? "").toLowerCase() === email.toLowerCase())) throw new ApiError(409, "an account with this email exists");
  const a: Account = {
    id: `k-${list.length + 1}`,
    name: body.name.trim(),
    email,
    customerNumber: body.customerNumber.trim(),
    deliveryAddress: "",
    isDemo: false,
    setup: { kitchen: false, rules: false, agent: false, done: false },
    agent: { state: "none", versions: [] },
    createdAt: new Date().toISOString(),
  };
  write(ACCOUNTS, [...list, { ...a, password: body.password }]);
  return enter(a);
}

export async function logout(): Promise<void> {
  sessionMemory = null;
  write(SESSION, null);
}
