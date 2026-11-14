import { defineConfig } from "@playwright/test";

// Runs against the built SPA in fixture mode. Screenshots go to
// ../../artifacts/shots (gitignored), one per page at 1280 and 390 px in
// both themes. playwright.scenes.config.ts runs the scenes against the backend.
const PORT = 5411;

export default defineConfig({
  testDir: "e2e",
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, viewport: { width: 1280, height: 900 }, colorScheme: "dark" },
  // accounts-demo walks the real backend: playwright.accounts.config.ts, `make accounts-e2e`
  testIgnore: ["live/**", "accounts-demo.spec.ts"],
  webServer: {
    command: `npx vite build && npx vite preview --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
