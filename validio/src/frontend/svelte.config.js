import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** @type {import('@sveltejs/kit').Config} */
export default {
  preprocess: vitePreprocess(),
  kit: {
    // A single page app: the backend serves build/ and falls back to index.html.
    adapter: adapter({ fallback: "index.html" }),
    alias: { "@arlen/ui-kit": "./vendor/arlen-ui-kit/src/lib" },
  },
};
