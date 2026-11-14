// Words of the start page (01, 02) and the ingest page (03, 04). Owner: P1.
// Shared words (edition names, finding words, footer) come from ./shared.

import { fmtNum } from '../format'
import { mins, numWord } from './shared'

export const HERO = 'See where seven Wikipedias disagree'
export const LEAD = 'Pick an article and see what each language edition tells differently'
export const SEARCH_PLACEHOLDER = 'Search any Wikipedia article'
export const SEARCH_LABEL = 'Search any Wikipedia article'
export const PREPARED_LEAD = 'Or open a prepared article'
export const EXAMPLE = 'Example'
/** "Example · Winter War". */
export function exampleKicker(topic: string): string {
  return `${EXAMPLE} · ${topic}`
}
export const OPEN_EXAMPLE = 'Open this comparison →'
/** What the live example statement is about. Written by hand for the known example statement (adapt/start.ts EXAMPLE_STATEMENT). */
export const EXAMPLE_SUBJECT = 'the Mainila shots'
/** Live example heading: "How four editions tell the Mainila shots". */
export function exampleTitle(editions: number, subject: string = EXAMPLE_SUBJECT): string {
  return `How ${numWord(editions)} editions tell ${subject}`
}
/** Right column of a prepared article when no year span is known: "7 editions". */
export function editionCount(n: number): string {
  return n === 1 ? '1 edition' : `${n} editions`
}

// Search result status, right side of a result row
export const READY = 'Ready'
export const LOADING = 'Loading now'
export const NO_FINNISH = 'Cannot be loaded'
/** "6 min to load". */
export function toLoad(etaS: number): string {
  return `${mins(etaS)} to load`
}
export const NO_RESULTS = 'No article found'
export const SEARCHING = 'Searching'
export const SEARCH_FAILED = 'Search is not available right now'

// Ingest
export const READING = 'Reading the full edit history in seven languages. You can close this tab and come back from search'
/** "About 4 min left". */
export function left(etaS: number): string {
  return `About ${mins(etaS)} left`
}
export const DONE = 'Done'
export const WAITING = 'Waiting'
export const FAILED = 'Could not load'
/** An edition that has no article on this topic. */
export const NO_ARTICLE = 'No article'
/** "91%". */
export function pct(n: number): string {
  return `${fmtNum(Math.round(n))}%`
}
/** "Compare the 4 ready editions". */
export function compareReady(n: number): string {
  return `Compare the ${n} ready editions`
}
export const OPEN_COMPARISON = 'Open the comparison'
/** "Faster: load only 2021 to 2026, about 1 min". */
export function faster(fromYear: number, toYear: number, etaS: number): string {
  return `Faster: load only ${fromYear} to ${toYear}, about ${mins(etaS)}`
}
export const INGEST_FAILED = 'Loading this article failed'
export const NO_FINNISH_LONG = 'This article has no Finnish version, so Parallax cannot compare it'
export const INGEST_NOT_FOUND = 'There is no loading job for this article'
export const START_AGAIN = 'Start loading'
export const LOAD_FAILED = 'Could not read the loading state. Trying again'
