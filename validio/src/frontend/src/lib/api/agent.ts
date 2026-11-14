// The kitchen's agent and its Rules (docs/ACCOUNTS-API.md, "Agent" and "Rules").
// `VITE_API=live` talks to /api; anything else plays the contract in this
// browser, kept in localStorage so a reload keeps it, as the backend would.

import { ApiError } from "./error";
import { session } from "../owner.svelte";
import type { AgentState, Rules, RulesDiet, RulesIn } from "./types";

export type { AgentState, Rules, RulesDiet, RulesIn };
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

// One fixture per kitchen, so a kitchen made here does not see the demo's agent.
const key = () => `validio-agent-mock-v2-${session.account?.id ?? "none"}`;
const HOST = typeof location === "undefined" ? "http://127.0.0.1" : location.origin;
const CODE = /^\d{6}$/;

interface Mock {
  agent: AgentState;
  rules: Rules;
  wrong: number;
}

const euro = (c: number) => `${(c / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;

/** The Rules in words, as the server writes `consent.may`. */
export function mayWords(r: Rules): string[] {
  if (!r.saved) return ["Every order needs approval"];
  return [
    `Orders alone up to ${euro(r.aloneUpToCents)}`,
    `Needs approval up to ${euro(r.approvalUpToCents)}`,
    `Blocked above ${euro(r.approvalUpToCents)}`,
    ...(r.perWeekCents == null ? [] : [`Per week up to ${euro(r.perWeekCents)}`]),
    r.substitutes === "off" ? "No substitutes" : r.substitutes === "listed" ? "Substitutes from Valio's list" : `Substitutes up to ${r.maxExtraPct} % extra`,
    ...(r.diet?.mustBe.length ? [`Only ${r.diet.mustBe.join(", ")}`] : []),
    ...(r.diet?.never.length ? [`Never ${r.diet.never.join(", ")}`] : []),
  ];
}

const DIET_OPTIONS: RulesDiet["options"] = {
  mustBe: ["lactose-free", "gluten-free", "vegan"],
  // As the server lists them (settings.py, NEVER_ALLERGENS): the EU's fourteen allergens.
  never: ["milk", "eggs", "gluten", "nuts", "peanuts", "soy", "fish", "crustaceans", "molluscs", "sesame", "celery", "mustard", "lupin", "sulphites"],
};

// A fresh demo copy as the server makes it: rules saved (api/settings.DEMO_RULES), no
// agent yet; an MCP agent connects itself. A kitchen made here: nothing saved, no agent.
function start(): Mock {
  if (!session.account?.isDemo)
    return {
      agent: { state: "none", versions: [] },
      rules: { aloneUpToCents: 0, approvalUpToCents: 0, perWeekCents: null, substitutes: "off", maxExtraPct: 0, saved: false, passVersion: 0, diet: { mustBe: [], never: [], options: DIET_OPTIONS } },
      wrong: 0,
    };
  return {
    agent: {
      state: "none",
      versions: [
        { version: 2, at: "2026-11-14T10:44:00+02:00", why: "Rules changed" },
        { version: 1, at: "2026-11-14T10:00:00+02:00", why: "Agent connected" },
      ],
    },
    rules: {
      aloneUpToCents: 120000,
      approvalUpToCents: 500000,
      perWeekCents: 800000,
      substitutes: "extra",
      maxExtraPct: 5,
      saved: true,
      passVersion: 2,
      diet: { mustBe: ["lactose-free"], never: [], options: DIET_OPTIONS },
    },
    wrong: 0,
  };
}

const memory: Record<string, Mock> = {};

function load(): Mock {
  try {
    const raw = localStorage.getItem(key());
    if (raw) return JSON.parse(raw) as Mock;
  } catch {
    // no storage: keep it in memory
  }
  return (memory[key()] ??= start());
}

function store(m: Mock): void {
  memory[key()] = m;
  try {
    localStorage.setItem(key(), JSON.stringify(m));
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
function randomCode(n: number): string {
  let s = "";
  for (let i = 0; i < n; i++) s += LOOK[Math.floor(Math.random() * LOOK.length)];
  return `${s.slice(0, n / 2)}-${s.slice(n / 2)}`;
}
const pairCode = () => randomCode(8);

function token(): string {
  const b = new Uint8Array(24);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

/** Fixture only: an MCP agent made its first call on the pairing URL, as the server then shows it.
 *  The agent gets the same verification code in its tool answer; returned here for the console. */
export function mockMcpCall(): string | undefined {
  const m = load();
  if (m.agent.state !== "pairing") return;
  const verifyCode = randomCode(6);
  m.agent = { state: "consent", consent: { name: "MCP agent", keyId: "m4Rt8Kpz", may: mayWords(m.rules), verifyCode, at: now() }, versions: m.agent.versions };
  store(m);
  return verifyCode;
}

/** Fixture only: the demo Reset puts this kitchen's agent and rules back to the start. */
export function resetMock(): void {
  delete memory[key()];
  try {
    localStorage.removeItem(key());
  } catch {
    // see load()
  }
}
// In the browser console of the fixture build: validioMcpCall()
if (!LIVE && typeof window !== "undefined") (window as unknown as { validioMcpCall: () => string | undefined }).validioMcpCall = mockMcpCall;

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
        // Any MCP agent: its first call asks for consent as "MCP agent".
        mcpUrl: `${HOST}/mcp/c/${token()}/`,
        apiUrl: `${HOST}/agent/v1/k/${session.account?.id ?? "k-demo"}`,
      },
      versions: m.agent.versions,
    };
    store(m);
    return structuredClone(m.agent);
  },
  async allow(): Promise<AgentState> {
    const m = load();
    const c = m.agent.consent;
    if (m.agent.state !== "consent" || !c) throw new ApiError(409, "nothing to allow");
    m.agent = { state: "active", versions: m.agent.versions };
    m.agent.agent = { name: c.name, kind: "mcp", keyId: c.keyId, connectedAt: now(), lastUsedAt: null, passId: "M-1", passVersion: 0 };
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
    // A demo kitchen takes its demo code only, as the server does; a kitchen made here any 6 digits.
    const demoCode = session.account?.demoCode;
    if (!CODE.test(body.code) || (demoCode && body.code !== demoCode)) {
      m.wrong += 1;
      store(m);
      throw new ApiError(403, "wrong approval code");
    }
    const max = 10_000_000;
    if ([body.aloneUpToCents, body.approvalUpToCents].some((c) => !(c >= 0) || c > max)) throw new ApiError(422, "an amount is out of range");
    if (body.aloneUpToCents > body.approvalUpToCents) throw new ApiError(422, "orders alone must not be above needs approval");
    if (body.perWeekCents != null && body.perWeekCents < body.approvalUpToCents) throw new ApiError(422, "per week is below needs approval");
    if (body.diet) {
      const bad = [...body.diet.mustBe.filter((w) => !DIET_OPTIONS.mustBe.includes(w)), ...body.diet.never.filter((w) => !DIET_OPTIONS.never.includes(w))];
      if (bad.length) throw new ApiError(422, `unknown diet word ${bad.map((w) => `'${w}'`).join(", ")}`);
    }
    m.wrong = 0;
    const diet = body.diet ? { ...body.diet, options: m.rules.diet?.options ?? DIET_OPTIONS } : m.rules.diet;
    m.rules = { ...m.rules, ...body, diet, saved: true };
    delete (m.rules as Partial<RulesIn>).code;
    bumpVersion(m, "Rules changed");
    store(m);
    return structuredClone(m.rules);
  },
};

export const agentApi = {
  /** Fixture only (see resetMock). */
  resetMock,
  agent: (): Promise<AgentState> => (LIVE ? call("GET", "/api/agent") : mock.agent()),
  pair: (): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/pair") : mock.pair()),
  allow: (): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/allow") : mock.allow()),
  deny: (): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/deny") : mock.deny()),
  pause: (paused: boolean): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/pause", { paused }) : mock.pause(paused)),
  disconnect: (): Promise<AgentState> => (LIVE ? call("POST", "/api/agent/disconnect") : mock.disconnect()),
  /** Money, substitutes and (v2) diet in one; one save is one new pass version. */
  rules: (): Promise<Rules> => (LIVE ? call("GET", "/api/rules") : mock.rules()),
  saveRules: (body: RulesIn): Promise<Rules> => (LIVE ? call("PUT", "/api/rules", body) : mock.saveRules(body)),
};

