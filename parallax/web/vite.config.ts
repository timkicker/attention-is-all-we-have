/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vue and Codex stay out of the bundle: index.html maps both to jsDelivr through an import map.
const external = ['vue', '@wikimedia/codex']

export default defineConfig({
  plugins: [vue()],
  build: { rolldownOptions: { external } },
  server: {
    port: Number(process.env.WEB_PORT ?? 5173),
    strictPort: true,
    proxy: { '/api': `http://127.0.0.1:${process.env.API_PORT ?? 8000}` },
  },
  test: { environment: 'jsdom', include: ['src/**/*.test.ts'], maxWorkers: 2 },
})
