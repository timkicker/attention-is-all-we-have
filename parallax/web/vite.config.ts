/// <reference types="vitest/config" />
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'

// Each agent points the dev server at its own API with API_PORT (default 8047).
const env = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {}
const API = `http://127.0.0.1:${env.API_PORT ?? 8047}`

export default defineConfig({
  plugins: [svelte()],
  resolve: { alias: { '@arlen/ui-kit': new URL('./vendor/arlen-ui-kit/src/lib', import.meta.url).pathname } },
  server: {
    // Compile every component at start so the first page never gets a raw .svelte as its CSS.
    warmup: { clientFiles: ['./src/**/*.svelte'] },
    proxy: { '/api': API },
  },
  test: { include: ['src/**/*.test.ts'], environment: 'node', maxWorkers: 2 },
})
