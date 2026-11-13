import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";

// The state the pages are audited in: R-1 ordered alone, the stock-out simulated, R-2 and O-2 waiting,
// the Steady Order not yet renewed (the keyboard test renews it).
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
  agent(1);
  agent(2);
  if (!(await post("/api/demo/stock-out")).ok) throw new Error("stock-out failed");
  agent(3);
}
