import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

// `make demo-smoke`: the public-deploy shape. One FastAPI process serves the built web app
// (VITE_API=live, built by the make target first) and the API, accounts in their own store, no template
// (every demo copy is the plain seed); no Vite server. Its own port (SMOKE_PORT, default 8416), so a
// `make demo` on 8410 is never touched; it refuses to start when something already answers there.
// The browser logs in through the login page as a demo copy, the agent is a real MCP client
// (e2e-live/kitchen.ts). SMOKE_BASE=https://... runs it against a running server or the public link.
// The server reads the web app from build/, which the default config rebuilds in mock mode: do not run
// both at once.
const REMOTE = process.env.SMOKE_BASE?.replace(/\/$/, "");
const PORT = process.env.SMOKE_PORT || "8416";
const BASE = REMOTE || `http://127.0.0.1:${PORT}`;
// Only the main process checks; the test workers load this file again once the server is up.
let busy = !REMOTE && !process.env.TEST_WORKER_INDEX;
if (busy) {
  try {
    execFileSync("curl", ["-s", "-o", "/dev/null", "--max-time", "2", `${BASE}/api/health`]);
  } catch {
    busy = false; // nothing answers
  }
}
if (busy) throw new Error(`something already answers on ${BASE}; stop it or set SMOKE_PORT`);
const STORE = resolve("../../artifacts/live-smoke");
if (!REMOTE)
  Object.assign(process.env, {
    VALIDIO_DB: `${STORE}/local/validio.db`, VALIDIO_KEYS: `${STORE}/local/keys`,
    VALIDIO_ACCOUNTS: `${STORE}/accounts`, VALIDIO_TEMPLATE: `${STORE}/template`,
    VALIO_MODE: "replay", VALIDIO_DEMO: "1", VALIDIO_APPROVE_CODE: "", VALIDIO_DEMO_TOKEN: "",
    VALIDIO_PUBLIC: "", VALIDIO_PUBLIC_READ: "", VALIDIO_KITCHEN_TOKEN: "", GEMINI_API_KEY: "",
  });

export default defineConfig({
  testDir: "e2e-live",
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  outputDir: `${STORE}-results`,
  use: { baseURL: BASE, viewport: { width: 1280, height: 900 }, trace: "retain-on-failure" },
  webServer: REMOTE
    ? undefined
    : {
        command:
          `rm -rf ${STORE} && mkdir -p ${STORE}/local && cd ../backend && ` +
          `uv run uvicorn validio.api.app:app --host 127.0.0.1 --port ${PORT}`,
        url: `${BASE}/api/health`,
        reuseExistingServer: false,
        timeout: 180_000,
      },
});
