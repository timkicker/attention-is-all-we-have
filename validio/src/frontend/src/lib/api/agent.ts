// The kitchen's agent and its Rules (docs/ACCOUNTS-API.md, "Agent" and "Rules").
// `VITE_API=live` talks to /api; anything else plays the contract in this
// browser, kept in localStorage so a reload keeps it, as the backend would.

import { ApiError } from "./error";
import type { AgentState, Rules, RulesIn } from "./types";

export type { AgentState, Rules, RulesIn };
export type Substitutes = Rules["substitutes"];

const LIVE = import.meta.env.VITE_API === "live";

async function call<T>(method: "GET" | "POST" | "PUT", path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: "include",
    headers: { accept: "application/json", ...(body === undefined ? {} : { "content-type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const b = await res.json();
      if (b?.detail) detail = String(b.detail);
    } catch {
      // not JSON, keep the status line
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

// ---------- the fixture ----------

const KEY = "validio-agent-mock-v1";
const HOST = typeof location === "undefined" ? "http://127.0.0.1" : location.origin;
const ACCOUNT = "k-demo";
const CODE = /^\d{6}$/;

interface Mock {
  agent: AgentState;
  rules: Rules;
  wrong: number;
}

const euro = (c: number) => `${(c / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;

/** The Rules in words, as the server writes `consent.may`. */
export function mayWords(r: Rules): string[] {
  if (!r.saved) return ["Ask you before every order"];
  return [
    `Order alone up to ${euro(r.aloneUpToCents)}`,
    `Ask you up to ${euro(r.approvalUpToCents)}`,
    `Never above ${euro(r.approvalUpToCents)}`,
    r.substitutes === "off" ? "No substitutes" : r.substitutes === "listed" ? "Substitutes from Valio's list" : `Substitutes up to ${r.maxExtraPct} % extra`,
  ];
}

// A fresh demo copy: rules saved, no agent yet, so "Connect the demo agent" is the first thing on the page.
function start(): Mock {
  return {
    agent: { state: "none", versions: [{ version: 1, at: "2026-11-14T09:10:00+02:00", why: "Rules changed" }] },
    rules: { aloneUpToCents: 120000, approvalUpToCents: 200000, substitutes: "listed", maxExtraPct: 5, saved: true, passVersion: 1 },
    wrong: 0,
  };
}

let memory: Mock | undefined;

function load(): Mock {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as Mock;
  } catch {
    // no storage: keep it in memory
  }
  return (memory ??= start());
}

function store(m: Mock): void {
  memory = m;
  try {
    localStorage.setItem(KEY, JSON.stringify(m));
  } catch {
    // see load()
  }
}

const now = () => new Date().toISOString();
const later = (ms: number) => new Promise((r) => setTimeout(r, ms));

function bumpVersion(m: Mock, why: string): number {
  const v = (m.agent.versions[0]?.version ?? 0) + 1;
  m.agent.versions.unshift({ version: v, at: now(), why });
  m.rules.passVersion = v;
  if (m.agent.agent) m.agent.agent.passVersion = v;
  return v;
}

const LOOK = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
function pairCode(): string {
  let s = "";
  for (let i = 0; i < 8; i++) s += LOOK[Math.floor(Math.random() * LOOK.length)];
  return `${s.slice(0, 4)}-${s.slice(4)}`;
}

const mock = {
  async agent(): Promise<AgentState> {
    return structuredClone(load().agent);
  },
  async pair(): Promise<AgentState> {
    const m = load();
    m.agent = {
      state: "pairing",
      pairing: {
        code: pairCode(),
        expiresAt: new Date(Date.now() + 10 * 60_000).toISOString(),
        mcpUrl: `${HOST}/mcp/k/${ACCOUNT}/`,
        apiUrl: `${HOST}/agent/v1/k/${ACCOUNT}`,
      },
      versions: m.agent.versions,
    };
    store(m);
    return structuredClone(m.agent);
  },
  async demo(): Promise<AgentState> {
    await later(300);
    const m = load();
    m.agent = { state: "consent", consent: { name: "Demo kitchen agent", keyId: "q3Hk7pXa", may: mayWords(m.rules) }, versions: m.agent.versions };
    store(m);
    return structuredClone(m.agent);
  },
  async allow(): Promise<AgentState> {
    const m = load();
    const c = m.agent.consent;
    if (m.agent.state !== "consent" || !c) throw new ApiError(409, "nothing to allow");
    m.agent = { state: "active", versions: m.agent.versions };
    m.agent.agent = { name: c.name, keyId: c.keyId, connectedAt: now(), lastUsedAt: null, passId: "M-1", passVersion: 0 };
    bumpVersion(m, "Agent connected");
    store(m);
    return structuredClone(m.agent);
  },
  async deny(): Promise<AgentState> {
    const m = load();
    m.agent = { state: "none", versions: m.agent.versions };
    store(m);
    return structuredClone(m.agent);
  },
  async pause(paused: boolean): Promise<AgentState> {
    const m = load();
    if (m.agent.state !== "active" && m.agent.state !== "paused") throw new ApiError(409, "no agent connected");
    m.agent.state = paused ? "paused" : "active";
    store(m);
    return structuredClone(m.agent);
  },
  async disconnect(): Promise<AgentState> {
    const m = load();
    bumpVersion(m, "Agent disconnected");
    m.agent = { state: "none", versions: m.agent.versions };
    store(m);
    return structuredClone(m.agent);
  },
  async rules(): Promise<Rules> {
    return structuredClone(load().rules);
  },
  async saveRules(body: RulesIn): Promise<Rules> {
    await later(200);
    const m = load();
    if (m.wrong >= 5) throw new ApiError(429, "too many wrong codes, wait 15 minutes");
    if (!CODE.test(body.code)) {
      m.wrong += 1;
      store(m);
      throw new ApiError(403, "wrong approval code");
    }
    const max = 10_000_000;
    if ([body.aloneUpToCents, body.approvalUpToCents].some((c) => !(c >= 0) || c > max)) throw new ApiError(422, "an amount is out of range");
    if (body.aloneUpToCents > body.approvalUpToCents) throw new ApiError(422, "orders alone must not be above needs approval");
    m.wrong = 0;
    m.rules = { ...m.rules, ...body, saved: true };
    delete (m.rules as Partial<RulesIn>).code;
    bumpVersion(m, "Rules changed");
    store(m);
    return structuredClone(m.rules);
  },
};

export const agentApi = {
  agent: (): Promise<AgentState> => (LIVE ? call("GET", "/api/agent") : mock.agent()),
  pair: (): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/pair") : mock.pair()),
  /** Demo copies only: the server's demo agent answers the code. */
  demo: (): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/demo") : mock.demo()),
  allow: (): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/allow") : mock.allow()),
  deny: (): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/deny") : mock.deny()),
  pause: (paused: boolean): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/pause", { paused }) : mock.pause(paused)),
  disconnect: (): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/disconnect") : mock.disconnect()),
  rules: (): Promise<Rules> => (LIVE ? call("GET", "/api/rules") : mock.rules()),
  saveRules: (body: RulesIn): Promise<Rules> => (LIVE ? call("PUT", "/api/rules", body) : mock.saveRules(body)),
};

