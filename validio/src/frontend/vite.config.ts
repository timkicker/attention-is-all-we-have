import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// The backend the dev server hands /api, /agent/v1 and /mcp to; VALIDIO_BACKEND moves it off 8410.
const env = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {};
const BACKEND = env.VALIDIO_BACKEND || "http://127.0.0.1:8410";

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    fs: { allow: ["."] },
    warmup: { clientFiles: ["./src/**/*.svelte"] },
    // In live mode the dev server hands the backend's routes to it, the MCP connector included.
    proxy: { "/api": BACKEND, "/agent/v1": BACKEND, "/mcp": BACKEND },
  },
});
