// Data for one page: fetched at once, again every two seconds (the owner may
// answer on the phone meanwhile), and again at once after a demo action.
// Whatever `fn` reads before its first await (a route param) is tracked, so a
// new param fetches the new thing. With a `key`, the last answer is kept
// (live-cache.ts) and a revisit renders it at once while it fetches again.
import { ApiError } from "./api/error";
import { chrome } from "./chrome.svelte";
import { cacheGet, cacheHas, cacheSet } from "./live-cache";
import { reportFail, reportOk } from "./net.svelte";
import { session } from "./owner.svelte";
import { poll } from "./poll";

export function live<T>(fn: () => Promise<T>, ms = 2000, key?: () => string) {
  // status: the HTTP status of the last failed fetch (404: the thing is not there), 0 when it did not answer.
  // fromCache: what is shown came from the cache, not yet from a fetch.
  // arrive: the first data came from a fetch after a skeleton, so the page makes its one entrance
  // (plans/004); set once, never unset, so a later answer does not replay it.
  const s = $state({ data: undefined as T | undefined, error: "", status: 0, loaded: false, fromCache: false, arrive: false });
  $effect(() => {
    void chrome.version;
    const k = key ? `${session.account?.id ?? "-"}:${key()}` : "";
    if (k && cacheHas(k)) {
      s.data = cacheGet(k) as T;
      s.loaded = true;
      s.fromCache = true;
    }
    return poll(async (alive) => {
      try {
        const data = await fn();
        if (!alive()) return; // the page moved on (a new param): this answer is for the old one
        if (s.data === undefined) s.arrive = true;
        s.data = data;
        s.error = "";
        s.status = 0;
        s.fromCache = false;
        if (k) cacheSet(k, data);
        reportOk();
      } catch (e) {
        if (!alive()) return;
        s.error = e instanceof Error ? e.message : String(e);
        s.status = e instanceof ApiError ? e.status : 0;
        if (!(e instanceof ApiError)) reportFail();
      } finally {
        if (alive()) s.loaded = true;
      }
    }, ms);
  });
  return s;
}
