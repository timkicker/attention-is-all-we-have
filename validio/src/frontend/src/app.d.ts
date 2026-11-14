/// <reference types="@sveltejs/kit" />
interface ImportMetaEnv {
  /** "live" talks to the Validio backend, anything else serves the fixture in src/lib/api/mock.ts. */
  readonly VITE_API?: string;
}
