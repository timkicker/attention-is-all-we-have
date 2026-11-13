/// <reference types="@sveltejs/kit" />
interface ImportMetaEnv {
  /** "live" talks to the Validio backend, anything else serves the recorded answers in snapshots/states.ts. */
  readonly VITE_API?: string;
}
