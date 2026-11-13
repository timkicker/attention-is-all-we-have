// The one place the pages get data from. `VITE_API=live` talks to the Validio
// backend under /api; anything else serves the answers the real backend gave,
// recorded in snapshots/states.ts (see mock.ts).

import { ApiError } from "./error";
import * as mock from "./mock";
import { owner } from "../owner.svelte";
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

export { ApiError };
export const LIVE = import.meta.env.VITE_API === "live";

async function call<T>(method: "GET" | "POST", path: string, headers: Record<string, string> = {}): Promise<T> {
  const res = await fetch(path, { method, headers: { accept: "application/json", ...headers } });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // not JSON, keep the status line
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const get = <T>(path: string) => call<T>("GET", path);
const post = <T>(path: string, headers?: Record<string, string>) => call<T>("POST", path, headers);
// Every write carries the approval code once the owner typed it; the demo
// switches carry the presenter's token. A server with neither set ignores them.
const write = <T>(path: string) => post<T>(path, owner.code ? { "x-approve-code": owner.code } : {});
const demo = <T>(path: string) => post<T>(path, owner.demoToken ? { "x-demo-token": owner.demoToken } : {});
const id = encodeURIComponent;

export const api = {
  inbox: (): Promise<InboxItem[]> => (LIVE ? get("/api/inbox") : mock.inbox()),
  request: (rid: string): Promise<SupplyRequest> =>
    LIVE ? get(`/api/requests/${id(rid)}`) : mock.request(rid),
  spendPass: (pid: string): Promise<SpendPass> =>
    LIVE ? get(`/api/spend-passes/${id(pid)}`) : mock.spendPass(pid),
  order: (oid: string): Promise<Order> => (LIVE ? get(`/api/orders/${id(oid)}`) : mock.order(oid)),
  approve: (oid: string): Promise<Order> =>
    LIVE ? write(`/api/orders/${id(oid)}/approve`) : mock.approve(oid, owner.code),
  reject: (oid: string): Promise<Order> =>
    LIVE ? write(`/api/orders/${id(oid)}/reject`) : mock.reject(oid, owner.code),
  ledger: (): Promise<Ledger> => (LIVE ? get("/api/ledger") : mock.ledger()),
  steadyList: (): Promise<SteadyOrderSummary[]> => (LIVE ? get("/api/steady") : mock.steadyList()),
  steadyOrder: (sid: string): Promise<SteadyOrder> =>
    LIVE ? get(`/api/steady/${id(sid)}`) : mock.steadyOrder(sid),
  renew: (sid: string): Promise<SteadyOrder> =>
    LIVE ? write(`/api/steady/${id(sid)}/renew`) : mock.renew(sid, owner.code),
  acceptLine: (sid: string, pid: string): Promise<SteadyOrder> =>
    LIVE ? write(`/api/steady/${id(sid)}/lines/${id(pid)}/accept`) : mock.acceptLine(sid, pid, owner.code),
  demoState: (): Promise<DemoState> => (LIVE ? get("/api/demo") : mock.demoState()),
  stockOut: (): Promise<DemoState> => (LIVE ? demo("/api/demo/stock-out") : mock.stockOut()),
  reset: (): Promise<DemoState> => (LIVE ? demo("/api/demo/reset") : mock.reset()),
};
