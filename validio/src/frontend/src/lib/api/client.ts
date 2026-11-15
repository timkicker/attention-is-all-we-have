// The one place the pages get data from (Agent and Rules: agent.ts, Settings:
// settings.ts). `VITE_API=live` talks to the Validio backend under /api;
// anything else plays the contract in this browser (mock.ts). The shapes are
// UI-V2-API.md.

import { ApiError, needsToken, tokenPrompt } from "./error";
import * as mock from "./mock";
import { owner, session } from "../owner.svelte";
import type {
  Account,
  ActivityDetail,
  ActivityFilter,
  ActivityList,
  DemoState,
  HomeOut,
  Ledger,
  LoginIn,
  ProofEntry,
  Order,
  SignupIn,
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
  /** Home in one call: agent status, the week, what needs the owner, the newest five. */
  home: (): Promise<HomeOut> => (LIVE ? get("/api/home") : mock.home()),
  /** The timeline, newest first, with the count of every filter. */
  activity: (status: ActivityFilter = "all"): Promise<ActivityList> =>
    LIVE ? get(`/api/activity?status=${status}`) : mock.activity(status),
  /** One request or standing order, top to bottom: asked, checked, rule, result, proof. */
  activityItem: (aid: string): Promise<ActivityDetail> => (LIVE ? get(`/api/activity/${id(aid)}`) : mock.activityItem(aid)),
  /** The request as Validio decided it, with every option it compared (Activity's detail shows them as a table).
   *  The fixture plays the v2 contract only and has none: 404, and the page goes without the table. */
  request: (rid: string): Promise<SupplyRequest> => (LIVE ? get(`/api/requests/${id(rid)}`) : mock.request(rid)),
  /** Approve sends owner.code as X-Approve-Code; set it first. */
  approve: (oid: string): Promise<Order> =>
    both(() => write(`/api/orders/${id(oid)}/approve`), () => mock.approve(oid, owner.code)),
  reject: (oid: string): Promise<Order> =>
    both(() => write(`/api/orders/${id(oid)}/reject`), () => mock.reject(oid)),
  /** Proof's Verify (plans/025, P4): the server checks the whole chain (ChainStatus), and every entry of
   *  this item is matched to the entry before it by its hash. The fixture has no ledger: it plays a sound one. */
  verifyProof: async (proof: ProofEntry[]): Promise<{ ok: boolean; count: number; links: boolean[]; head: string | null }> => {
    if (!LIVE) {
      await new Promise((r) => setTimeout(r, 250));
      return { ok: true, count: proof.length + 12, links: proof.map(() => true), head: proof.at(-1)?.at ?? null };
    }
    const l = await get<Ledger>("/api/ledger");
    const at = new Map(l.entries.map((e, i) => [e.hash, i]));
    const links = proof.map((p) => {
      const i = at.get(p.hash);
      if (i === undefined) return false;
      return i === 0 || l.entries[i].prevHash === l.entries[i - 1].hash;
    });
    return { ok: l.chain.ok && links.every(Boolean), count: l.chain.count, links, head: l.entries.at(-1)?.at ?? null };
  },
  /** Demo kitchens only: back to the sample data. */
  reset: (): Promise<DemoState> => both(() => demo("/api/demo/reset"), () => mock.reset()),
};
