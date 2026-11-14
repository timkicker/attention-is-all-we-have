// The web app without a backend. Every answer here is one the real backend
// gave, recorded by scripts/snapshots.py into snapshots/states.ts; nothing is
// invented. The demo controls only move between recorded states:
//
//   mozzarella request: none -> (stock-out) waiting -> placed | rejected
//   steady order:       pending -> (renew) renewed -> accepted | mozzarella | both
//
// The state lives in localStorage so a reload keeps it, as the backend would.

import { money } from "$lib/format";
import { answers, refused, states } from "./snapshots/states";
import { ApiError } from "./error";
import type {
  AskOut,
  DemoState,
  InboxItem,
  Ledger,
  Order,
  SpendPass,
  SpendPassIn,
  SteadyOrder,
  SteadyOrderSummary,
  SupplyRequest,
} from "./types";

type Moz = "none" | "waiting" | "placed" | "rejected";
type Steady = "pending" | "renewed" | "accepted" | "mozzarella" | "both";
interface State {
  moz: Moz;
  steady: Steady;
  /** The stock-out ended again; the recorded answers stay where they were. */
  back?: boolean;
  /** The limits the owner signed in this browser, laid over the recorded pass. */
  pass?: Pick<SpendPassIn, "autoLimitCents" | "hardCapCents" | "diet" | "deliverBy" | "substitutes">;
}

const KEY = "validio-mock-v2";
const START: State = { moz: "none", steady: "pending" };
const PANCAKES = "471376";
const MOZZARELLA = "466375";

let memory: State = { ...START };

function load(): State {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const s = JSON.parse(raw) as State;
      if (states[`${s.moz}-${s.steady}`]) return s;
    }
  } catch {
    // no storage in this browser: keep the state in memory
  }
  return memory;
}

function save(s: State): void {
  memory = s;
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    // see load()
  }
}

function pick(s: State): Record<string, number> {
  return states[`${s.moz}-${s.steady}`];
}

function copy<T>(v: T): T {
  return structuredClone(v);
}

function notFound(what: string): never {
  throw new ApiError(404, `${what} not found`);
}

/** The recorded answer at `path` for the current state, from `list`. */
function at<T>(path: string, list: T[] | undefined): T {
  const i = pick(load())[path];
  if (i === undefined || !list) notFound(path);
  return copy(list[i]);
}

/** The fixture plays a server with the approval code set: any 6 digits pass. */
function checkCode(code: string): void {
  if (!/^\d{6}$/.test(code)) throw new ApiError(403, "wrong or missing approval code");
}

export async function inbox(): Promise<InboxItem[]> {
  return at("/api/inbox", answers.inbox);
}

export async function request(id: string): Promise<SupplyRequest> {
  return at(`/api/requests/${id}`, answers.requests[id]);
}

const DIET: Record<string, string> = { FREE_FROM_LACTOSE: "lactose free", FREE_FROM_GLUTEN: "gluten free", VEGAN: "vegan" };

export async function spendPass(id: string): Promise<SpendPass> {
  const p = at(`/api/spend-passes/${id}`, answers.spendPass[id]);
  const o = load().pass;
  if (!o) return p;
  return {
    ...p,
    autoLimitCents: o.autoLimitCents,
    hardCapCents: o.hardCapCents,
    diet: o.diet.map((d) => DIET[d] ?? d),
    deliverBy: o.deliverBy,
    substitutes: o.substitutes ? p.substitutes : "never",
    split: { ...p.split, allowListedSubstitutes: o.substitutes },
  };
}

/** Signing again: the fixture keeps the new limits for the Spend Pass page; recorded decisions stay as they were. */
export async function signPass(body: SpendPassIn, code: string): Promise<SpendPass> {
  checkCode(body.code ?? code);
  if (body.autoLimitCents > body.hardCapCents) throw new ApiError(422, `alone up to ${money(body.autoLimitCents)} is above never above ${money(body.hardCapCents)}`);
  const { autoLimitCents, hardCapCents, diet, deliverBy, substitutes } = body;
  save({ ...load(), pass: { autoLimitCents, hardCapCents, diet, deliverBy, substitutes } });
  return spendPass("M-1");
}

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

/** No agent runs without the backend: the fixture says so instead of inventing an answer. */
export async function ask(text: string): Promise<AskOut> {
  if (!text.trim()) throw new ApiError(422, "say what the kitchen needs");
  return { model: "none", lines: [], final: "This build has no backend, so no agent can ask. Start it with make demo to try your own text." };
}

export async function order(id: string): Promise<Order> {
  return at(`/api/orders/${id}`, answers.orders[id]);
}

async function decide(id: string, code: string, to: "placed" | "rejected"): Promise<Order> {
  const s = load();
  const current = await order(id);
  checkCode(code);
  if (current.state !== "waiting") throw new ApiError(409, `order ${id} is ${current.state}, not waiting`);
  // Only the mozzarella order ever waits for the owner in the demo.
  save({ ...s, moz: to });
  return order(id);
}

export const approve = (id: string, code: string) => decide(id, code, "placed");
export const reject = (id: string, code: string) => decide(id, code, "rejected");

export async function ledger(): Promise<Ledger> {
  return at("/api/ledger", answers.ledger);
}

export async function steadyList(): Promise<SteadyOrderSummary[]> {
  return at("/api/steady", answers.steadyList);
}

export async function steadyOrder(id: string): Promise<SteadyOrder> {
  return at(`/api/steady/${id}`, answers.steady[id]);
}

export async function renew(id: string, code: string): Promise<SteadyOrder> {
  const s = load();
  await steadyOrder(id);
  checkCode(code);
  if (s.steady !== "pending") throw new ApiError(409, "this week's order is already renewed");
  save({ ...s, steady: "renewed" });
  return steadyOrder(id);
}

export async function acceptLine(id: string, productId: string, code: string): Promise<SteadyOrder> {
  const s = load();
  await steadyOrder(id);
  checkCode(code);
  const both = (s.steady === "accepted" && productId === MOZZARELLA) || (s.steady === "mozzarella" && productId === PANCAKES);
  const next: Steady | undefined = both
    ? "both"
    : s.steady === "renewed" && productId === PANCAKES
      ? "accepted"
      : s.steady === "renewed" && productId === MOZZARELLA
        ? "mozzarella"
        : undefined;
  if (!next) throw new ApiError(409, `line ${productId} is not waiting`);
  const key = `${s.moz}-${next}`;
  if (refused[key]) throw new ApiError(409, refused[key]);
  save({ ...s, steady: next });
  return steadyOrder(id);
}

export async function demoState(): Promise<DemoState> {
  const d = at("/api/demo", answers.demo);
  return load().back ? { ...d, stockOut466375: false } : d;
}

/**
 * The stock-out switch. With the backend the kitchen's agent then asks again;
 * the fixture jumps to the answer that run gave: the request waits for the owner.
 */
export async function stockOut(on = true): Promise<DemoState> {
  const s = load();
  if (!on) {
    // Ending it: the mozzarella request keeps the state it reached.
    if (s.moz !== "none") save({ ...s, back: true });
    return demoState();
  }
  if (s.back) save({ ...s, back: false });
  if (s.moz === "none") {
    // An accepted mozzarella line cannot stay accepted once the stock is gone.
    const steady: Steady = s.steady === "mozzarella" ? "renewed" : s.steady === "both" ? "accepted" : s.steady;
    save({ ...load(), moz: "waiting", steady });
  }
  return demoState();
}

export async function reset(): Promise<DemoState> {
  save({ ...START });
  return demoState();
}
