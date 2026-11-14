// Words of the four states (12): loading, filter shows nothing, one edition failed,
// date before the article existed. Owner: P4. Used by lib/ui/states/*.svelte.

import { fmtDate, numWord } from '../format'
import { edition, mins } from './shared'

export const LOADING = 'Loading'
/** "No statement matches “volunteers” on 1 Jan 2008" (date null = today). */
export function noMatch(q: string, date: string | null): string {
  return date ? `No statement matches “${q}” on ${fmtDate(date)}` : `No statement matches “${q}”`
}
export const CLEAR_SEARCH = 'Clear search'
/** "Russian could not load. Wikipedia asked us to slow down". */
export function editionFailed(lang: string, rateLimited: boolean): string {
  return rateLimited ? `${edition(lang)} could not load. Wikipedia asked us to slow down` : `${edition(lang)} could not load`
}
/** "The other six are ready". */
export function othersReady(n: number): string {
  return `The other ${numWord(n)} are ready`
}
export const OPEN_THEM = 'Open them'
/** "Retrying in 2 min". */
export function retryingIn(seconds: number): string {
  return `Retrying in ${mins(seconds)}`
}
/** "Estonian had no article on 12 Mar 2004. It starts on 8 Jun 2006". */
export function beforeArticle(lang: string, date: string, startsOn: string): string {
  return `${edition(lang)} had no article on ${fmtDate(date)}. It starts on ${fmtDate(startsOn)}`
}
/** "Show every edition on 8 Jun 2006". */
export function showEveryEditionOn(date: string): string {
  return `Show every edition on ${fmtDate(date)}`
}

// Captions of the dev-only states page (/dev/states), as in wireframe 12
export const CAP_LOADING = 'State: loading'
export const CAP_EMPTY = 'State: filter shows nothing'
export const CAP_FAILED = 'State: one edition failed'
export const CAP_BEFORE = 'State: date before the article existed'
