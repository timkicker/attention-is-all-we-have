import { defineConfig } from "@playwright/test";

// The scenes against the real backend: the SPA built with VITE_API=live and
// served by the backend itself, which e2e/live/serve.py starts with the
// approval code and the demo token set and fills with scenes 1 to 3.
//   npx playwright test -c playwright.scenes.config.ts
const PORT = Number(process.env.LIVE_PORT ?? 8433);

export default defineConfig({
  testDir: "e2e/live",
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, viewport: { width: 1280, height: 900 }, colorScheme: "dark" },
  webServer: {
    command: `VITE_API=live npx vite build && cd ../backend && uv run python -W ignore ../frontend/e2e/live/serve.py`,
    // R-2 exists only once serve.py has played the agent's half of scene 3.
    url: `http://127.0.0.1:${PORT}/api/requests/R-2`,
    reuseExistingServer: false,
    timeout: 300_000,
    stdout: "pipe",
  },
});
