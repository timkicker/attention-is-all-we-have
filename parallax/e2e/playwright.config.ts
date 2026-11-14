// End to end checks against the API serving the built web app (make web-build first).
// E2E_URL points at a running instance. Without it Playwright loads seed-mini into its own database parallax_e2e
// (the specs assert seed-mini rows, whatever seed the main database holds) and starts uvicorn on it on E2E_PORT.
import { defineConfig, devices } from '@playwright/test'

const port = Number(process.env.E2E_PORT ?? 8057)
const db = 'DB_NAME=parallax_e2e SEED=mini ENGINE=fake'
const external = process.env.E2E_URL

export default defineConfig({
  testDir: '.',
  outputDir: 'results',
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: external ?? `http://127.0.0.1:${port}`,
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
  webServer: external
    ? undefined
    : {
        command:
          `${db} uv run python scripts/load_sql.py --create --reset contract/schema.sql contract/fixtures/seed-mini.sql` +
          ` && ${db} uv run uvicorn api.main:app --host 127.0.0.1 --port ${port}`,
        cwd: '..',
        url: `http://127.0.0.1:${port}/api/health`,
        reuseExistingServer: false,
        timeout: 30_000,
      },
})
