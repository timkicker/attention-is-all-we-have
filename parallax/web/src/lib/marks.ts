// Text with highlighted ranges: build from words, split into segments for rendering.

import type { MarkedText, Span } from './model'

/** Marks the first occurrence of each word, in order: marked("A staged B", "staged"). */
export function marked(text: string, ...words: string[]): MarkedText {
  const spans: Span[] = []
  let from = 0
  for (const w of words) {
    const i = text.indexOf(w, from)
    if (i < 0) continue
    spans.push({ start: i, end: i + w.length })
    from = i + w.length
  }
  return { text, spans }
}

/** The whole text as one span (a statement removed entirely). */
export function all(text: string): MarkedText {
  return { text, spans: [{ start: 0, end: text.length }] }
}

/** Plain text, nothing marked. */
export function plain(text: string): MarkedText {
  return { text, spans: [] }
}

export interface Segment {
  text: string
  on: boolean
}

/** Splits text into plain and marked segments. Overlapping or out-of-range spans are clipped. */
export function segments({ text, spans }: MarkedText): Segment[] {
  const out: Segment[] = []
  let at = 0
  for (const s of [...spans].sort((a, b) => a.start - b.start)) {
    const start = Math.max(at, Math.min(s.start, text.length))
    const end = Math.max(start, Math.min(s.end, text.length))
    if (start > at) out.push({ text: text.slice(at, start), on: false })
    if (end > start) out.push({ text: text.slice(start, end), on: true })
    at = end
  }
  if (at < text.length) out.push({ text: text.slice(at), on: false })
  return out
}
