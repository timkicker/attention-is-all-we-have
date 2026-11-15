// Every page's last answer, so a revisit renders at once and refetches meanwhile (plans/003).
// Keys carry the account id; a demo reset or another account forgets everything.
const cache = new Map<string, unknown>();
const primed = new Map<string, number>();

export const cacheGet = (key: string): unknown => cache.get(key);
export const cacheHas = (key: string): boolean => cache.has(key);
export const cacheSet = (key: string, value: unknown): void => void cache.set(key, value);

/** Forget every page's last answer (a demo reset, another account). */
export function forgetLive(): void {
  cache.clear();
  primed.clear();
}

/** Fetch ahead on intent (a pointer resting on a row) and keep the answer for the page (plans/020).
 *  At most once per key every 10 s; errors are ignored, the page asks again anyway. */
export function prime(key: string, run: () => Promise<unknown>): void {
  const last = primed.get(key) ?? 0;
  if (Date.now() - last < 10_000) return;
  primed.set(key, Date.now());
  run().then(
    (v) => cache.set(key, v),
    () => {},
  );
}
