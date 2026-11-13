import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

// `make demo-smoke`: the public-deploy shape. One FastAPI process serves the built web app
// (VITE_API=live, built by the make target first) and the API from a store seeded for this run; no
// Vite server. Its own port (SMOKE_PORT, default 8416), so a `make demo` on 8410 is never touched;
// it refuses to start when something already answers there. The approve code and demo token are
// switched off, as the web client sends neither yet.
const PORT = process.env.SMOKE_PORT || "8416";
const BASE = `http://127.0.0.1:${PORT}`;
// Only the main process checks; the test workers load this file again once the server is up.
let busy = !process.env.TEST_WORKER_INDEX;
if (busy) {
  try {
    execFileSync("curl", ["-s", "-o", "/dev/null", "--max-time", "2", `${BASE}/api/health`]);
  } catch {
    busy = false; // nothing answers
  }
}
if (busy) throw new Error(`something already answers on ${BASE}; stop it or set SMOKE_PORT`);
process.env.SMOKE_BASE = BASE;
const STORE = resolve("../../artifacts/live-smoke");
process.env.VALIDIO_DB = `${STORE}/validio.db`;
process.env.VALIDIO_KEYS = `${STORE}/keys`;
process.env.VALIO_MODE = "replay";
process.env.VALIDIO_APPROVE_CODE = "";
process.env.VALIDIO_DEMO_TOKEN = "";
process.env.VALIDIO_DEMO = "1";

export default defineConfig({
  testDir: "e2e-live",
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: BASE, viewport: { width: 1280, height: 900 } },
  webServer: {
    command:
      `mkdir -p ${STORE} && cd ../backend && uv run python ../../scripts/seed_demo.py && ` +
      `uv run uvicorn validio.api.app:app --host 127.0.0.1 --port ${PORT}`,
    url: `${BASE}/api/health`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
