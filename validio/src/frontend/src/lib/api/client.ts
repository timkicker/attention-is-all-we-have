// The one place the pages get data from. `VITE_API=live` talks to the Validio
// backend under /api; anything else drives the pages from the fixture in
// mock.ts. The route names follow the blueprint ("Phone approval") and the
// build notes; once the backend's OpenAPI file exists this switches to
// openapi-fetch with generated types.

import * as mock from "./mock";
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

export const LIVE = import.meta.env.VITE_API === "live";

async function call<T>(method: "GET" | "POST", path: string): Promise<T> {
  const res = await fetch(path, { method, headers: { accept: "application/json" } });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // not JSON, keep the status line
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

const get = <T>(path: string) => call<T>("GET", path);
const post = <T>(path: string) => call<T>("POST", path);
const id = encodeURIComponent;

export const api = {
  inbox: (): Promise<InboxItem[]> => (LIVE ? get("/api/inbox") : mock.inbox()),
  request: (rid: string): Promise<SupplyRequest> =>
    LIVE ? get(`/api/requests/${id(rid)}`) : mock.request(rid),
  spendPass: (pid: string): Promise<SpendPass> =>
    LIVE ? get(`/api/spend-passes/${id(pid)}`) : mock.spendPass(pid),
  order: (oid: string): Promise<Order> => (LIVE ? get(`/api/orders/${id(oid)}`) : mock.order(oid)),
  approve: (oid: string): Promise<Order> =>
    LIVE ? post(`/api/orders/${id(oid)}/approve`) : mock.approve(oid),
  reject: (oid: string): Promise<Order> =>
    LIVE ? post(`/api/orders/${id(oid)}/reject`) : mock.reject(oid),
  ledger: (): Promise<Ledger> => (LIVE ? get("/api/ledger") : mock.ledger()),
  steadyList: (): Promise<SteadyOrderSummary[]> => (LIVE ? get("/api/steady") : mock.steadyList()),
  steadyOrder: (sid: string): Promise<SteadyOrder> =>
    LIVE ? get(`/api/steady/${id(sid)}`) : mock.steadyOrder(sid),
  renew: (sid: string): Promise<SteadyOrder> =>
    LIVE ? post(`/api/steady/${id(sid)}/renew`) : mock.renew(sid),
  acceptLine: (sid: string, pid: string): Promise<SteadyOrder> =>
    LIVE ? post(`/api/steady/${id(sid)}/lines/${id(pid)}/accept`) : mock.acceptLine(sid, pid),
  demoState: (): Promise<DemoState> => (LIVE ? get("/api/demo") : mock.demoState()),
  stockOut: (): Promise<DemoState> => (LIVE ? post("/api/demo/stock-out") : mock.stockOut()),
  /** Fixture only: back to the state `make demo` starts from. */
  reset: async (): Promise<void> => {
    if (LIVE) await post("/api/demo/reset");
    else mock.resetMock();
  },
};
