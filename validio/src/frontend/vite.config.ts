import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    fs: { allow: ["."] },
    warmup: { clientFiles: ["./src/**/*.svelte"] },
    // In live mode the dev server hands /api to the backend on 8410.
    proxy: { "/api": "http://127.0.0.1:8410", "/agent": "http://127.0.0.1:8410" },
  },
});
