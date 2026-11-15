// Whether the page is live: the polls report here (plans/020). Nothing polls on its own account.
export const net = $state({ lastOk: 0, failing: false, online: typeof navigator === "undefined" ? true : navigator.onLine, now: Date.now() });

export function reportOk(): void {
  net.lastOk = Date.now();
  net.failing = false;
}
export function reportFail(): void {
  net.failing = true;
}

/** The shared clock for relative times and the live mark; ticks only while someone listens. */
let ticking = 0;
let timer: ReturnType<typeof setInterval> | undefined;
export function tick(ms = 1000): () => void {
  ticking += 1;
  if (!timer) timer = setInterval(() => (net.now = Date.now()), ms);
  return () => {
    ticking -= 1;
    if (ticking <= 0 && timer) {
      clearInterval(timer);
      timer = undefined;
      ticking = 0;
    }
  };
}
