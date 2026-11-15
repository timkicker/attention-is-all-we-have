// Props from a primitive (a tooltip trigger) with our own on top: handlers named in both run
// both, the primitive's first; anything else of ours wins.
type Props = Record<string, unknown>;
export function merge(theirs: Props, ours: Props): Props {
  const out: Props = { ...theirs, ...ours };
  for (const [k, v] of Object.entries(ours)) {
    const t = theirs[k];
    if (k.startsWith("on") && typeof t === "function" && typeof v === "function")
      out[k] = (e: Event) => {
        (t as (e: Event) => void)(e);
        (v as (e: Event) => void)(e);
      };
  }
  return out;
}
