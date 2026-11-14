// Words of Check an AI answer (09) and its result (10). Owner: P3.
// Finding words ("In no edition", "Disputed", "Backed by") and checkSummary come from ./shared.
// Recorded-answer labels ("... on Mainila") are data from the API, never written here.

import { fmtDate } from '../format'
import { checkSummary } from './shared'

export const SUB_CHECK = 'Which editions back up what a chatbot says'
/** "Paste what a chatbot said about Winter War". */
export function placeholder(topic: string): string {
  return `Paste what a chatbot said about ${topic}`
}
export const ANSWER_LABEL = 'Answer to check'
export const RECORDED_LEAD = 'Or try a recorded answer:'
export const CHECK_ANSWER = 'Check answer'
export const CHECKING = 'Checking the answer'
/** "Gemini on Mainila · recorded 12 Nov 2026" (label is data). */
export function recordedOn(label: string, date: string | null): string {
  return date ? `${label} · recorded ${fmtDate(date)}` : label
}
export const PASTED = 'Your answer'
export const CHECK_ANOTHER = 'Check another answer'
export const SHOW_WHOLE = 'Show the whole answer'
export const SHOW_LESS = 'Show less'
export const EMPTY_ANSWER = 'Paste an answer to check'
export const TOO_LONG = 'The answer is too long. Paste at most 6,000 characters'

/**
 * The summary line. Shared checkSummary says "backed by most editions"; when some backed statement has
 * only a minority of editions behind it, that would overstate it, so the line says "at least one" instead.
 * (Workaround until copy/shared.ts checkSummary takes this flag itself.)
 */
export function summary(s: { total: number; none: number; disputed: number; backed: number }, most: boolean): string {
  const line = checkSummary(s)
  return most ? line : line.replace('backed by most editions', 'backed by at least one edition')
}
