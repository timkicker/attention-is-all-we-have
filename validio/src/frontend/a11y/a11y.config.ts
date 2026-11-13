import { execFileSync } from "node:child_process";
import { randomInt } from "node:crypto";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

// `make a11y`: axe-core (WCAG 2.2 A and AA, contrast included) over every route at 1280 and 390 px, light
// and dark, plus keyboard-only approve, renew and accept, visible focus and 44 px targets on the phone.
// Built app and API from one process on A11Y_PORT (8420), seeded for this run, replayed Valio answers,
// approve code on. Results per test go to artifacts/a11y/results, summary.mjs prints them per page.
const HERE = dirname(fileURLToPath(import.meta.url));
const PORT = process.env.A11Y_PORT || "8420";
const BASE = `http://127.0.0.1:${PORT}`;
if (!process.env.TEST_WORKER_INDEX) {
  let busy = true;
  try {
    execFileSync("curl", ["-sf", "-o", "/dev/null", "--max-time", "2", `${BASE}/api/health`]);
  } catch {
    busy = false;
  }
  if (busy) throw new Error(`something already answers on ${BASE}; stop it or set A11Y_PORT`);
}
process.env.A11Y_BASE = BASE;
process.env.A11Y_CODE ||= String(randomInt(0, 1_000_000)).padStart(6, "0"); // the workers inherit it
const STORE = resolve(HERE, "../../../artifacts/a11y-store");
process.env.A11Y_OUT = resolve(HERE, "../../../artifacts/a11y");
process.env.VALIDIO_DB = `${STORE}/validio.db`;
process.env.VALIDIO_KEYS = `${STORE}/keys`;
process.env.VALIO_MODE = "replay";
process.env.VALIDIO_DEMO = "1";
process.env.VALIDIO_APPROVE_CODE = process.env.A11Y_CODE;
process.env.VALIDIO_DEMO_TOKEN = "";

export default defineConfig({
  testDir: ".",
  testMatch: "*.audit.ts",
  globalSetup: "./setup.ts",
  workers: 1,
  fullyParallel: false,
  timeout: 120_000,
  reporter: [["list"]],
  use: { baseURL: BASE },
  webServer: {
    command:
      `rm -rf ${STORE} && mkdir -p ${STORE} && cd ../../backend && uv run python ../../scripts/seed_demo.py && ` +
      `uv run uvicorn validio.api.app:app --host 127.0.0.1 --port ${PORT}`,
    url: `${BASE}/api/health`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
