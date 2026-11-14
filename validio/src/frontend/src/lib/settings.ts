// Settings and the demo's example request (docs/ACCOUNTS-API.md, sections
// Settings and Demo). `VITE_API=live` talks to the backend; the fixture keeps
// the kitchen's settings in localStorage, as the backend would keep them.
import { api, ApiError, LIVE } from "$lib/api/client";
import type { AskOut, Diet, Settings } from "$lib/api/types";
import { session } from "$lib/owner.svelte";

export type { Diet, Settings };
export const DIETS: { id: Diet; label: string }[] = [
  { id: "FREE_FROM_LACTOSE", label: "Lactose free" },
  { id: "FREE_FROM_GLUTEN", label: "Gluten free" },
  { id: "VEGAN", label: "Vegan" },
];

/** The challenge's sentence, as the demo agent sends it. */
export const EXAMPLE = "1000 litres of lactose-free milk by Monday, budget 1200 euro";

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
  return (res.status === 204 ? undefined : await res.json()) as T;
}

// The fixture: each account's settings start from its account, lactose free
// as the recorded pass; changes stay in localStorage per account.
const key = () => `validio-mock-settings-${session.account?.id ?? "none"}`;
const memory: Record<string, Settings> = {};

function load(): Settings {
  try {
    const raw = localStorage.getItem(key());
    if (raw) return JSON.parse(raw) as Settings;
  } catch {
    // no storage: memory only
  }
  const a = session.account;
  return structuredClone(
    memory[key()] ?? {
      kitchen: { name: a?.name ?? "", customerNumber: a?.customerNumber ?? "", deliveryAddress: a?.deliveryAddress ?? "" },
      diet: ["FREE_FROM_LACTOSE"],
      login: { email: a?.email ?? null },
    },
  );
}
function save(s: Settings): Settings {
  memory[key()] = s;
  try {
    localStorage.setItem(key(), JSON.stringify(s));
  } catch {
    // see load()
  }
  return structuredClone(s);
}

/** After a kitchen change: the sidebar's name and the Inbox checklist follow. */
export async function refreshAccount(s: Settings) {
  if (LIVE) {
    session.account = await api.account();
    return;
  }
  const a = session.account;
  if (!a) return;
  const kitchen = !!(s.kitchen.name && s.kitchen.deliveryAddress);
  const setup = { ...a.setup, kitchen };
  setup.done = setup.kitchen && setup.rules && setup.agent;
  session.account = { ...a, name: s.kitchen.name, deliveryAddress: s.kitchen.deliveryAddress, setup };
  // The fixture's session (api/mock.ts) keeps it over a reload, as the server would.
  try {
    localStorage.setItem("validio-mock-session", JSON.stringify(session.account));
  } catch {
    // no storage: this visit only
  }
}
const later = <T>(v: T) => new Promise<T>((r) => setTimeout(() => r(v), 150));
function checkCode(code: string) {
  if (!/^\d{6}$/.test(code)) throw new ApiError(403, "wrong approval code");
}

export const settingsApi = {
  get: (): Promise<Settings> => (LIVE ? call("GET", "/api/settings") : later(load())),
  kitchen: async (b: { name: string; deliveryAddress: string }): Promise<Settings> => {
    if (LIVE) return call("PUT", "/api/settings/kitchen", b);
    if (!b.name.trim()) throw new ApiError(422, "name is empty");
    const s = load();
    return later(save({ ...s, kitchen: { ...s.kitchen, name: b.name.trim(), deliveryAddress: b.deliveryAddress.trim() } }));
  },
  diet: async (diet: Diet[], code: string): Promise<Settings> => {
    if (LIVE) return call("PUT", "/api/settings/diet", { diet, code });
    checkCode(code);
    return later(save({ ...load(), diet }));
  },
  login: async (b: { currentPassword: string; email?: string; password?: string }): Promise<Settings> => {
    if (LIVE) return call("PUT", "/api/settings/login", b);
    if (b.currentPassword.length < 8) throw new ApiError(403, "wrong password");
    const s = load();
    return later(save({ ...s, login: { email: b.email ?? s.login.email } }));
  },
  approvalCode: async (b: { current: string; next: string }): Promise<void> => {
    if (LIVE) return call("PUT", "/api/settings/approval-code", b);
    checkCode(b.current);
    if (!/^\d{6}$/.test(b.next)) throw new ApiError(422, "next must be 6 digits");
    await later(null);
  },
  /** The demo agent sends the challenge's sentence. The fixture points at the recorded milk request. */
  example: (): Promise<AskOut> =>
    LIVE ? call("POST", "/api/demo/example") : later({ requestId: "R-1", model: "fixture", lines: [], final: "Ordered alone." }),
};
