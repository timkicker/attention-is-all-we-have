// The web app without a backend. Every answer here is one the real backend
// gave, recorded by scripts/snapshots.py into snapshots/states.ts; nothing is
// invented. The demo controls only move between recorded states:
//
//   mozzarella request: none -> (stock-out) waiting -> placed | rejected
//   steady order:       pending -> (renew) renewed -> accepted | mozzarella | both
//
// The state lives in localStorage so a reload keeps it, as the backend would.

import { answers, refused, states } from "./snapshots/states";
import { ApiError } from "./error";
import type {
  DemoState,
  InboxItem,
  Ledger,
  Order,
  SpendPass,
  SteadyOrder,
  SteadyOrderSummary,
  SupplyRequest,
} from "./types";

type Moz = "none" | "waiting" | "placed" | "rejected";
type Steady = "pending" | "renewed" | "accepted" | "mozzarella" | "both";
interface State {
  moz: Moz;
  steady: Steady;
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

export async function spendPass(id: string): Promise<SpendPass> {
  return at(`/api/spend-passes/${id}`, answers.spendPass[id]);
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
  return at("/api/demo", answers.demo);
}

/**
 * The stock-out switch. With the backend the kitchen's agent then asks again;
 * the fixture jumps to the answer that run gave: the request waits for the owner.
 */
export async function stockOut(): Promise<DemoState> {
  const s = load();
  if (s.moz === "none") {
    // An accepted mozzarella line cannot stay accepted once the stock is gone.
    const steady: Steady = s.steady === "mozzarella" ? "renewed" : s.steady === "both" ? "accepted" : s.steady;
    save({ moz: "waiting", steady });
  }
  return demoState();
}

export async function reset(): Promise<DemoState> {
  save({ ...START });
  return demoState();
}
