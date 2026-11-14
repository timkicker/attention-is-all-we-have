// Words of Check an AI answer (09) and its result (10). Owner: P3.
// Finding words ("In no edition", "Disputed", "Backed by") and checkSummary come from ./shared.
// Recorded-answer labels ("... on Mainila") are data from the API, never written here.

import { fmtDate } from '../format'
import { DISPUTED, fmtNum } from './shared'

/** "Disputed · in 2 of 7, removed in 4 editions" (more than two editions removed it). */
export function disputedRemovedIn(n: number, of: number, removedIn: number): string {
  return `${DISPUTED} · in ${n} of ${of}, removed in ${fmtNum(removedIn)} editions`
}

/** Short topic phrases for the recorded questions (a label stays under 30 characters): "Gemini on Mainila". */
export const QUESTION_TOPICS: readonly (readonly [RegExp, string])[] = [
  [/mainila/i, 'Mainila'],
  [/died|killed|losses|lost/i, 'Finnish losses'],
  [/territory|cede/i, 'ceded land'],
  [/terijoki/i, 'Terijoki'],
  [/\bwar end/i, 'the war\'s end'],
]

export const SUB_CHECK = 'Which editions back up what a chatbot says'
/** "Paste what a chatbot said about the Winter War". */
export function placeholder(topic: string): string {
  return `Paste what a chatbot said about ${/^the /i.test(topic) ? topic : `the ${topic}`}`
}
export const ANSWER_LABEL = 'Answer to check'
export const RECORDED_LEAD = 'Or try a recorded answer:'
export const CHECK_ANSWER = 'Check answer'
export const CHECKING = 'Checking the answer'
/** "Gemini on Mainila · recorded 12 Nov 2026" (label is data). */
export function recordedOn(label: string, date: string | null): string {
  return date ? `${label} · ${recordedDate(date)}` : label
}
/** "recorded 12 Nov 2026" (the meta line keeps it on one line). */
export function recordedDate(date: string): string {
  return `recorded ${fmtDate(date)}`
}
export const PASTED = 'Your answer'
export const CHECK_ANOTHER = 'Check another answer'
export const SHOW_WHOLE = 'Show the whole answer'
export const SHOW_LESS = 'Show less'
export const EMPTY_ANSWER = 'Paste an answer to check'
export const TOO_LONG = 'The answer is too long. Paste at most 6,000 characters'
