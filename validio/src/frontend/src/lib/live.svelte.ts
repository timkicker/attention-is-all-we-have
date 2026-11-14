// Data for one page: fetched at once, again every two seconds (the owner may
// answer on the phone meanwhile), and again at once after a demo action.
// Whatever `fn` reads before its first await (a route param) is tracked, so a
// new param fetches the new thing.
import { ApiError } from "./api/error";
import { chrome } from "./chrome.svelte";
import { poll } from "./poll";

export function live<T>(fn: () => Promise<T>, ms = 2000) {
  // status: the HTTP status of the last failed fetch (404: the thing is not there), 0 when it did not answer
  const s = $state({ data: undefined as T | undefined, error: "", status: 0, loaded: false });
  $effect(() => {
    void chrome.version;
    return poll(async (alive) => {
      try {
        const data = await fn();
        if (!alive()) return; // the page moved on (a new param): this answer is for the old one
        s.data = data;
        s.error = "";
        s.status = 0;
      } catch (e) {
        if (!alive()) return;
        s.error = e instanceof Error ? e.message : String(e);
        s.status = e instanceof ApiError ? e.status : 0;
      } finally {
        if (alive()) s.loaded = true;
      }
    }, ms);
  });
  return s;
}
