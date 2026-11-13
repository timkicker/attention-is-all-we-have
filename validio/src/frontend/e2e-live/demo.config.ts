import { execFileSync } from "node:child_process";
import { randomInt } from "node:crypto";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

// `make e2e-live`: the 10:00 click-through of docs/DEMO.md in a browser against the live backend.
// One FastAPI process serves the built web app (VITE_API=live) and the API from a store seeded for
// this run, replayed Valio answers. Its own port (E2E_PORT, default 8419), so `make demo` on 8410,
// demo-smoke on 8416 and demo-check on 8418 are never touched. The approve code is on (approve,
// Steady renew and accept need it); the demo token is off, the presenter's Simulate button sends none.
// E2E_STRICT=1 turns a missing data-testid into a failure instead of a fixme.
const PORT = process.env.E2E_PORT || "8419";
const BASE = `http://127.0.0.1:${PORT}`;
// Only the main process checks; the test workers load this file again once the server is up.
if (!process.env.TEST_WORKER_INDEX) {
  let busy = true;
  try {
    execFileSync("curl", ["-sf", "-o", "/dev/null", "--max-time", "2", `${BASE}/api/health`]);
  } catch {
    busy = false; // nothing answers
  }
  if (busy) throw new Error(`something already answers on ${BASE}; stop it or set E2E_PORT`);
}
process.env.E2E_BASE = BASE;
process.env.E2E_CODE ||= String(randomInt(0, 1_000_000)).padStart(6, "0"); // the workers inherit it
const STORE = resolve(dirname(fileURLToPath(import.meta.url)), "../../../artifacts/e2e-live");
process.env.VALIDIO_DB = `${STORE}/validio.db`;
process.env.VALIDIO_KEYS = `${STORE}/keys`;
process.env.VALIO_MODE = "replay";
process.env.VALIDIO_DEMO = "1";
process.env.VALIDIO_APPROVE_CODE = process.env.E2E_CODE;
process.env.VALIDIO_DEMO_TOKEN = "";

export default defineConfig({
  testDir: ".",
  testMatch: "*.demo.ts", // not *.spec.ts: playwright.live.config.ts (demo-smoke) runs this folder too
  workers: 1,
  fullyParallel: false,
  timeout: 120_000,
  reporter: [["list"]],
  use: { baseURL: BASE, viewport: { width: 1280, height: 900 } },
  webServer: {
    command:
      `mkdir -p ${STORE} && cd ../../backend && uv run python ../../scripts/seed_demo.py && ` +
      `uv run uvicorn validio.api.app:app --host 127.0.0.1 --port ${PORT}`,
    url: `${BASE}/api/health`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
