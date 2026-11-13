// Data for one page: fetched at once, again every two seconds (the owner may
// answer on the phone meanwhile), and again at once after a demo action.
// Whatever `fn` reads before its first await (a route param) is tracked, so a
// new param fetches the new thing.
import { chrome } from "./chrome.svelte";
import { poll } from "./poll";

export function live<T>(fn: () => Promise<T>, ms = 2000) {
  const s = $state({ data: undefined as T | undefined, error: "", loaded: false });
  $effect(() => {
    void chrome.version;
    return poll(async () => {
      try {
        s.data = await fn();
        s.error = "";
      } catch (e) {
        s.error = e instanceof Error ? e.message : String(e);
      } finally {
        s.loaded = true;
      }
    }, ms);
  });
  return s;
}
