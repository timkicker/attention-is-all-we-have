// Ask again every `ms`, the way the inbox waits for the owner's answer.
export function poll(fn: () => Promise<void>, ms = 2000): () => void {
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const tick = async () => {
    try {
      await fn();
    } finally {
      if (!stopped) timer = setTimeout(tick, ms);
    }
  };
  tick();
  return () => {
    stopped = true;
    clearTimeout(timer);
  };
}
