import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

// The accounts "Done means" path (e2e/accounts-demo.spec.ts) against the real backend, as the public link
// serves it: the web app built with VITE_API=live, the demo template played the way `make template` plays
// it, accounts in their own store, one FastAPI process on ACCOUNTS_PORT (default 8417).
//   npx playwright test -c playwright.accounts.config.ts
// Against a running server or the public link instead, without this config:
//   ACCOUNTS_BASE=https://... npx playwright test e2e/accounts-demo.spec.ts
// The server reads the web app from build/, which the default config rebuilds in mock mode: do not run
// both at once.
const PORT = process.env.ACCOUNTS_PORT || "8417";
const BASE = `http://127.0.0.1:${PORT}`;
let busy = !process.env.TEST_WORKER_INDEX;
if (busy) {
  try {
    execFileSync("curl", ["-s", "-o", "/dev/null", "--max-time", "2", `${BASE}/api/health`]);
  } catch {
    busy = false;
  }
}
if (busy) throw new Error(`something already answers on ${BASE}; stop it or set ACCOUNTS_PORT`);
process.env.ACCOUNTS_BASE = BASE;
const STORE = resolve("../../artifacts/accounts-e2e");
const flags = readFileSync(resolve("../../Makefile"), "utf8").match(/^template:\n\t.*demo_check\.py (.*?)--store/m);
if (!flags) throw new Error("the Makefile has no template target calling demo_check.py --store");
Object.assign(process.env, {
  VALIDIO_DB: `${STORE}/local/validio.db`, VALIDIO_KEYS: `${STORE}/local/keys`,
  VALIDIO_ACCOUNTS: `${STORE}/accounts`, VALIDIO_TEMPLATE: `${STORE}/template`,
  VALIO_MODE: "replay", VALIDIO_DEMO: "1", VALIDIO_APPROVE_CODE: "246810", VALIDIO_DEMO_TOKEN: "",
  VALIDIO_PUBLIC: "", VALIDIO_PUBLIC_READ: "", VALIDIO_KITCHEN_TOKEN: "", GEMINI_API_KEY: "",
});

export default defineConfig({
  testDir: "e2e",
  testMatch: "accounts-demo.spec.ts",
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  outputDir: "../../artifacts/accounts-e2e/results",
  use: { baseURL: BASE, viewport: { width: 1280, height: 900 }, trace: "retain-on-failure" },
  webServer: {
    command:
      `rm -rf ${STORE} && mkdir -p ${STORE}/local && VITE_API=live npx vite build && cd ../backend && ` +
      `uv run python -W ignore ../../scripts/demo_check.py ${flags[1].trim()} --store ${STORE}/template && ` +
      `uv run python ../../scripts/seed_demo.py && ` +
      `uv run uvicorn validio.api.app:app --host 127.0.0.1 --port ${PORT}`,
    url: `${BASE}/api/health`,
    reuseExistingServer: false,
    timeout: 300_000,
  },
});
