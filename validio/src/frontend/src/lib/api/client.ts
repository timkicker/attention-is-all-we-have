// The one place the pages get data from. `VITE_API=live` talks to the Validio
// backend under /api; anything else serves the answers the real backend gave,
// recorded in snapshots/states.ts (see mock.ts).

import { ApiError, needsToken, tokenPrompt } from "./error";
import * as mock from "./mock";
import { owner, session } from "../owner.svelte";
import type {
  Account,
  DemoState,
  InboxItem,
  Ledger,
  LoginIn,
  Order,
  SpendPass,
  SpendPassIn,
  SteadyOrder,
  SignupIn,
  SteadyOrderSummary,
  SupplyRequest,
} from "./types";

export { ApiError, needsToken };
export const LIVE = import.meta.env.VITE_API === "live";

async function call<T>(method: "GET" | "POST", path: string, headers: Record<string, string> = {}, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: "include",
    headers: { accept: "application/json", ...(body === undefined ? {} : { "content-type": "application/json" }), ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // not JSON, keep the status line
    }
    // The session ran out: the layout sends the page to /login.
    if (res.status === 401 && !/^\/api\/account\/(login|signup|demo)/.test(path) && !/token/i.test(detail)) session.account = null;
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const get = <T>(path: string) => call<T>("GET", path);
const post = <T>(path: string, headers?: Record<string, string>, body?: unknown) => call<T>("POST", path, headers, body);
// Every write carries the approval code once the owner typed it, and the
// presenter's demo token once typed: on the public link that token opens the
// kitchen gate for writes. A server with neither set ignores them.
const token = (): Record<string, string> => (owner.demoToken ? { "x-demo-token": owner.demoToken } : {});
const write = <T>(path: string, body?: unknown) => post<T>(path, { ...(owner.code ? { "x-approve-code": owner.code } : {}), ...token() }, body);
const demo = <T>(path: string, body?: unknown) => post<T>(path, token(), body);

/** A write the server refused for want of the token asks for it once and runs again. */
async function gated<T>(run: () => Promise<T>): Promise<T> {
  try {
    return await run();
  } catch (e) {
    if (needsToken(e) && tokenPrompt.ask && (await tokenPrompt.ask())) return gated(run);
    throw e;
  }
}
// The fixture plays the same gate when a test sets a public token (mock.publicGate).
const both = <T>(live: () => Promise<T>, fixture: () => Promise<T>) =>
  gated(() => (LIVE ? live() : mock.publicGate(owner.demoToken).then(fixture)));
const id = encodeURIComponent;

export const api = {
  /** Who is logged in; 401 when nobody is. */
  account: (): Promise<Account> => (LIVE ? get("/api/account") : mock.account()),
  login: (body: LoginIn): Promise<Account> => (LIVE ? post("/api/account/login", {}, body) : mock.login(body)),
  signup: (body: SignupIn): Promise<Account> => (LIVE ? post("/api/account/signup", {}, body) : mock.signup(body)),
  /** A copy of the demo kitchen for this browser session (the same copy on reload). */
  demoLogin: (): Promise<Account> => (LIVE ? post("/api/account/demo") : mock.demoLogin()),
  logout: (): Promise<void> => (LIVE ? post("/api/account/logout") : mock.logout()),
  inbox: (): Promise<InboxItem[]> => (LIVE ? get("/api/inbox") : mock.inbox()),
  request: (rid: string): Promise<SupplyRequest> =>
    LIVE ? get(`/api/requests/${id(rid)}`) : mock.request(rid),
  spendPass: (pid: string): Promise<SpendPass> =>
    LIVE ? get(`/api/spend-passes/${id(pid)}`) : mock.spendPass(pid),
  order: (oid: string): Promise<Order> => (LIVE ? get(`/api/orders/${id(oid)}`) : mock.order(oid)),
  approve: (oid: string): Promise<Order> =>
    both(() => write(`/api/orders/${id(oid)}/approve`), () => mock.approve(oid, owner.code)),
  reject: (oid: string): Promise<Order> =>
    both(() => write(`/api/orders/${id(oid)}/reject`), () => mock.reject(oid, owner.code)),
  ledger: (): Promise<Ledger> => (LIVE ? get("/api/ledger") : mock.ledger()),
  steadyList: (): Promise<SteadyOrderSummary[]> => (LIVE ? get("/api/steady") : mock.steadyList()),
  steadyOrder: (sid: string): Promise<SteadyOrder> =>
    LIVE ? get(`/api/steady/${id(sid)}`) : mock.steadyOrder(sid),
  renew: (sid: string): Promise<SteadyOrder> =>
    both(() => write(`/api/steady/${id(sid)}/renew`), () => mock.renew(sid, owner.code)),
  acceptLine: (sid: string, pid: string): Promise<SteadyOrder> =>
    both(() => write(`/api/steady/${id(sid)}/lines/${id(pid)}/accept`), () => mock.acceptLine(sid, pid, owner.code)),
  demoState: (): Promise<DemoState> => (LIVE ? get("/api/demo") : mock.demoState()),
  /** The owner signs Spend Pass M-1 again with new limits; the code goes as X-Approve-Code. */
  signPass: (body: SpendPassIn): Promise<SpendPass> => both(() => write("/api/spend-pass", body), () => mock.signPass(body, owner.code)),
  reset: (): Promise<DemoState> => both(() => demo("/api/demo/reset"), () => mock.reset()),
};
