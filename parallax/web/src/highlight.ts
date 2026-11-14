// Split a sentence into plain and marked pieces so a differing number or term can be coloured in place.
export interface Piece {
  text: string
  kind?: 'number' | 'term'
}

export function highlight(text: string, needles: { text: string; kind: 'number' | 'term' }[]): Piece[] {
  const hits: { start: number; end: number; kind: 'number' | 'term' }[] = []
  const lower = text.toLowerCase()
  for (const n of needles) {
    if (!n.text) continue
    const at = lower.indexOf(n.text.toLowerCase())
    if (at < 0) continue
    const end = at + n.text.length
    if (hits.some((h) => at < h.end && end > h.start)) continue
    hits.push({ start: at, end, kind: n.kind })
  }
  hits.sort((a, b) => a.start - b.start)
  const out: Piece[] = []
  let pos = 0
  for (const h of hits) {
    if (h.start > pos) out.push({ text: text.slice(pos, h.start) })
    out.push({ text: text.slice(h.start, h.end), kind: h.kind })
    pos = h.end
  }
  if (pos < text.length) out.push({ text: text.slice(pos) })
  return out
}
