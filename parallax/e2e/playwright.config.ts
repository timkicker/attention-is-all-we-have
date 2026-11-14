// End to end checks against the API serving the built web app (make web-build first).
// E2E_URL points at a running instance; without it Playwright starts uvicorn on E2E_PORT with the loaded seed.
import { defineConfig, devices } from '@playwright/test'

const port = Number(process.env.E2E_PORT ?? 8000)
const external = process.env.E2E_URL

export default defineConfig({
  testDir: '.',
  outputDir: 'results',
  workers: 2,
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
        command: `uv run uvicorn api.main:app --host 127.0.0.1 --port ${port}`,
        cwd: '..',
        url: `http://127.0.0.1:${port}/api/health`,
        reuseExistingServer: true,
        timeout: 30_000,
      },
})
