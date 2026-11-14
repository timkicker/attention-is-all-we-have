// Label placement for the record plots: inside the box, no two overlapping,
// one row when the plot is wide (>= 480 px), two rows when it is narrow.
export const WIDE = 480;

export interface Want {
  text: string;
  /** Anchor x in px. */
  x: number;
  align: "center" | "left" | "right";
  /** Preferred row (0 or 1); a wide plot has only row 0. */
  row?: number;
  testid?: string;
  /** Never dropped: placed first. */
  keep?: boolean;
  /** The money part, for a screen reader and the tests. */
  html?: { before?: string; strong: string; after?: string };
}
export interface Placed extends Want {
  left: number;
  top: number;
  width: number;
  /** Set when the label ends at its anchor: it is placed by its right edge, so a
   * font that renders wider than measured still ends where it should. */
  right?: number;
}

let ctx: CanvasRenderingContext2D | null = null;
export function textWidth(s: string): number {
  if (typeof document === "undefined") return s.length * 6.5;
  ctx ??= document.createElement("canvas").getContext("2d");
  if (!ctx) return s.length * 6.5;
  ctx.font = '400 12px "Inter Variable", Inter, system-ui, sans-serif';
  return Math.ceil(ctx.measureText(s).width) + 2;
}

export function place(wants: Want[], width: number): Placed[] {
  const rows = width >= WIDE ? 1 : 2;
  const out: Placed[] = [];
  const order = [...wants].sort((a, b) => Number(!!b.keep) - Number(!!a.keep));
  for (const w of order) {
    const tw = textWidth(w.text);
    let align = w.align;
    if (align === "center") {
      if (w.x < tw / 2) align = "left";
      else if (w.x > width - tw / 2) align = "right";
    }
    let left = align === "center" ? w.x - tw / 2 : align === "left" ? w.x : w.x - tw;
    left = Math.max(0, Math.min(width - tw, left));
    const tries = rows === 1 ? [0] : [w.row ?? 0, 1 - (w.row ?? 0)];
    for (const row of tries) {
      const clash = out.some((p) => p.top === 40 + row * 16 && left < p.left + p.width + 8 && p.left < left + tw + 8);
      if (!clash) {
        const right = align === "right" || left + tw >= width - 1 ? Math.max(0, width - left - tw) : undefined;
        out.push({ ...w, left, top: 40 + row * 16, width: tw, right });
        break;
      }
    }
  }
  return out;
}
