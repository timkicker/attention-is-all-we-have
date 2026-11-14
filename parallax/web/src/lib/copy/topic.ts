// Words of the topic Differences tab (05, 07) and the one-statement page (06). Owner: P2.
// Finding words ("says it differently", "Not in", "same in the other ...") come from ./shared.
import { changedFromTo, edition, editions, fmtDate, numWord } from './shared'

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

/** "31 Dec 2022, ..." for an exact date, "By 31 Dec 2022, ..." when only a yearly copy dates it. */
export function changedFromToAt(date: string, approx: boolean, lang: string, from: string, to: string): string {
  const line = changedFromTo(date, lang, from, to)
  return approx ? `By ${line}` : line
}

/** The date part of a "When it changed" row, linked to that revision: "21 Aug 2009" (one format for exact and yearly dates). */
export function changeDate(date: string, _approx: boolean): string {
  return fmtDate(date)
}

/** The line under the date of a "When it changed" row. */
export function changeRest(lang: string, from: string, to: string): string {
  return `${edition(lang)} changed “${from}” to “${to}”`
}

/** The rest of the row for a removal: "Russian removed it". */
export function removedRest(lang: string): string {
  return `${edition(lang)} removed it`
}

/** Title of the edition label link. */
export function versionTitle(lang: string): string {
  return `This version in the ${edition(lang)} Wikipedia`
}

/** Between edition names in a group label: "Finnish, Swedish and German". */
export const LIST_SEP = ', '
export const LIST_AND = ' and '

/** Toggle on a long quote. */
export const MORE = 'more'
export const LESS = 'less'

/** "same in German" / "same in German and Swedish" (note line). */
export function sameInLangs(langs: readonly string[]): string {
  return `same in ${editions(langs)}`
}

/** "Show all 7" under the first changes. */
export function showAllChanges(n: number): string {
  return `Show all ${n}`
}

/** "not in Swedish" (note line, after the variants). */
export function notInLower(langs: readonly string[]): string {
  return `not in ${editions(langs)}`
}

/** Statement page heading: "Winter War: one statement in seven editions" (the wording itself is in each group). */
export function oneStatementIn(topic: string, editionCount: number): string {
  return editionCount > 1 ? `${topic}: one statement in ${numWord(editionCount)} editions` : `${topic}: one statement`
}

/** Next to an edition whose difference has no words to mark. */
export const SAYS_DIFFERENTLY = 'says it differently'
/** After the edition names of a group: "says it differently" / "say it differently". */
export function saysItDifferently(n: number): string {
  return n === 1 ? SAYS_DIFFERENTLY : 'say it differently'
}
