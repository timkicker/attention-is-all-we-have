/// <reference types="@sveltejs/kit" />
interface ImportMetaEnv {
  /** "live" talks to the Validio backend, anything else uses the fixture. */
  readonly VITE_API?: string;
}
