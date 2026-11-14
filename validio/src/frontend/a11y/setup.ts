import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";

// The state the pages are audited in, played by the demo agent into the local kitchen: R-1 ordered alone,
// R-2 waiting for approval (O-2), the Steady Order S-1 renewed with two lines waiting. The demo copy every
// test shares is taken from it and starts with no agent connected; the specs walk the agent states.
function agent(scene: number) {
  execFileSync("uv", ["run", "python", "-W", "ignore", "../../scripts/agent.py", "--scene", String(scene),
    "--base", process.env.A11Y_BASE!], { cwd: "../backend", env: process.env, stdio: "pipe" });
}

export default async function setup() {
  const out = `${process.env.A11Y_OUT}/results`;
  rmSync(out, { recursive: true, force: true });
  mkdirSync(out, { recursive: true });
  const post = (path: string) => fetch(`${process.env.A11Y_BASE}${path}`, { method: "POST" });
  if (!(await post("/api/demo/reset")).ok) throw new Error("reset failed");
  for (const scene of [1, 2, 3, 4]) agent(scene);
  // One demo copy of that state for every test, so the keyboard steps and the "after" scans share it.
  const r = await post("/api/account/demo");
  if (!r.ok) throw new Error("demo login failed");
  const cookie = r.headers.getSetCookie().map((c) => c.split(";")[0]).find((c) => c.startsWith("validio_session="));
  if (!cookie) throw new Error("no session cookie");
  const value = cookie.slice("validio_session=".length);
  const host = new URL(process.env.A11Y_BASE!).hostname;
  writeFileSync(process.env.A11Y_STATE!, JSON.stringify({
    cookies: [{ name: "validio_session", value, domain: host, path: "/", expires: -1, httpOnly: true, secure: false, sameSite: "Lax" }],
    origins: [],
  }));
}
