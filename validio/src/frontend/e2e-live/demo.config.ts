import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

// `make e2e-live`: the v2 pages in a browser against the live backend, on a demo copy as a juror gets it
// (e2e-live/kitchen.ts): login page, Try the demo kitchen, a real MCP client (scripts/connector_check.py)
// connected on the Agent page's URL (flow.demo.ts: order alone, lower Rules, approve, Pause, Disconnect;
// pages.demo.ts: a click through every page).
// Here one FastAPI process serves the built web app (VITE_API=live) and the API with accounts in their own
// store under artifacts/e2e-live, replayed Valio answers, its own port (E2E_PORT, default 8419), so
// `make demo` on 8410, demo-smoke on 8416, accounts-e2e on 8417 and demo-check on 8418 are never touched.
// The server reads the web app from build/, which the default Playwright config rebuilds in mock mode: do
// not run both at once.
// E2E_BASE=https://... runs the same tests against a running server or the public link instead, no server
// started here. Nothing in these two files needs the server's local store.
const REMOTE = process.env.E2E_BASE?.replace(/\/$/, "");
const PORT = process.env.E2E_PORT || "8419";
const BASE = REMOTE || `http://127.0.0.1:${PORT}`;
// Only the main process checks; the test workers load this file again once the server is up.
if (!REMOTE && !process.env.TEST_WORKER_INDEX) {
  let busy = true;
  try {
    execFileSync("curl", ["-sf", "-o", "/dev/null", "--max-time", "2", `${BASE}/api/health`]);
  } catch {
    busy = false; // nothing answers
  }
  if (busy) throw new Error(`something already answers on ${BASE}; stop it or set E2E_PORT`);
}
const STORE = resolve(dirname(fileURLToPath(import.meta.url)), "../../../artifacts/e2e-live");
if (!REMOTE)
  Object.assign(process.env, {
    VALIDIO_DB: `${STORE}/local/validio.db`, VALIDIO_KEYS: `${STORE}/local/keys`,
    VALIDIO_ACCOUNTS: `${STORE}/accounts`, VALIDIO_TEMPLATE: `${STORE}/template`, // no template: plain seeds
    VALIO_MODE: "replay", VALIDIO_DEMO: "1", VALIDIO_REAL_TIME: "1", VALIDIO_APPROVE_CODE: "", VALIDIO_DEMO_TOKEN: "",
    VALIDIO_PUBLIC: "", VALIDIO_PUBLIC_READ: "", VALIDIO_KITCHEN_TOKEN: "", GEMINI_API_KEY: "",
  });

export default defineConfig({
  testDir: ".",
  testMatch: "*.demo.ts", // not *.spec.ts: playwright.live.config.ts (demo-smoke) runs this folder too
  workers: 1,
  fullyParallel: false,
  timeout: 120_000,
  reporter: [["list"]],
  outputDir: `${STORE}-results`,
  use: { reducedMotion: "reduce", baseURL: BASE, viewport: { width: 1280, height: 900 }, trace: "retain-on-failure" },
  webServer: REMOTE
    ? undefined
    : {
        command:
          `rm -rf ${STORE} && mkdir -p ${STORE}/local && cd ../../backend && ` +
          `uv run uvicorn validio.api.app:app --host 127.0.0.1 --port ${PORT}`,
        url: `${BASE}/api/health`,
        reuseExistingServer: false,
        timeout: 180_000,
      },
});
