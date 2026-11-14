// Words of the topic Differences tab (05, 07) and the one-statement page (06). Owner: P2.
// Finding words ("says it differently", "Not in", "same in the other ...") come from ./shared.
import { changedFromTo, editions } from './shared'

export const SUB_DIFFERENCES = 'Statements where other editions tell it differently, with the differing part'
export const SUB_DIFFERENCES_MARK = 'marked'
export const SHOW_ORIGINAL = 'Show original wording'
export const SHOW_ENGLISH = 'Show English wording'
export const WHEN_IT_CHANGED = 'When it changed'
export const NO_CHANGES = 'No edition changed this statement'
export const NO_DIFFERENCES = 'Every edition tells this article the same way on this date'

// Number words in a note line ("German says about 25,000").
export const ABOUT = 'about'
export const UP_TO = 'up to'
export const OVER = 'over'
export const PERCENT = ' percent'

/** "Not compared yet in Russian and Estonian": a close sentence exists, but nobody compared it with this one. */
export function notCompared(langs: readonly string[]): string {
  return `Not compared yet in ${editions(langs)}`
}

/** "31 Dec 2022 · ..." for an exact date, "By 31 Dec 2022 · ..." when only a yearly copy dates it. */
export function changedFromToAt(date: string, approx: boolean, lang: string, from: string, to: string): string {
  const line = changedFromTo(date, lang, from, to)
  return approx ? `By ${line}` : line
}
