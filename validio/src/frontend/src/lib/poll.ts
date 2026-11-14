// Ask again every `ms`, the way the inbox waits for the owner's answer.
// A hidden tab asks nothing; it asks at once when it shows again. `fn` gets
// `alive()`: false once the poll stopped, so an answer that arrives after a
// stop (a new route param) is dropped instead of overwriting the new one.
export function poll(fn: (alive: () => boolean) => Promise<void>, ms = 2000): () => void {
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const alive = () => !stopped;
  const hidden = () => typeof document !== "undefined" && document.visibilityState === "hidden";
  const tick = async () => {
    clearTimeout(timer);
    try {
      if (!hidden()) await fn(alive);
    } finally {
      if (!stopped) timer = setTimeout(tick, ms);
    }
  };
  const shown = () => {
    if (!stopped && !hidden()) void tick();
  };
  if (typeof document !== "undefined") document.addEventListener("visibilitychange", shown);
  tick();
  return () => {
    stopped = true;
    clearTimeout(timer);
    if (typeof document !== "undefined") document.removeEventListener("visibilitychange", shown);
  };
}
