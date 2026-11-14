// Shared words of the app. Import them through lib/copy.ts, never from here directly in a page.
// Shared words live here: edition names, finding words, tabs, bar, footer, dates, numbers.
// A finding word ("says it differently", "Removed", "Disputed", "Backed by", "In no edition",
// "Not in", "same in the other ...") is written ONLY here. Area files (lib/copy/*.ts) hold
// sentences used by one area and import finding words from here, never retype them.
// Rules: sentence case, no exclamation marks, no trailing periods on labels, no Oxford comma,
// edition names written out, never a language code, never an AI vendor name.

import { fmtDate, fmtNum, joinNames, minutes, numWord } from '../format'
import type { Lang, Note, NotePart } from '../model'

export { fmtDate, fmtNum, joinNames, numWord } from '../format'

// ---------- Editions ----------

export const EDITION: Record<Lang, string> = {
  fi: 'Finnish',
  sv: 'Swedish',
  de: 'German',
  en: 'English',
  ru: 'Russian',
  et: 'Estonian',
  uk: 'Ukrainian',
}

/** "sv" -> "Swedish". An unknown code becomes "another edition", never the code itself. */
export function edition(lang: string): string {
  return (EDITION as Record<string, string>)[lang] ?? 'another edition'
}

/** ["sv", "en", "ru"] -> "Swedish, English and Russian". */
export function editions(langs: readonly string[]): string {
  return joinNames(langs.map(edition))
}

// ---------- Finding words ----------

const SEP: NotePart = { text: ', ', sep: true }
const says = (n: number) => (n === 1 ? 'says' : 'say')

/** Joins note groups; NoteLine sets them apart by space. */
export function note(...groups: Note[]): Note {
  const out: Note = []
  groups.filter((g) => g.length).forEach((g, i) => {
    if (i) out.push(SEP)
    out.push(...g)
  })
  return out
}

/** Plain text of a note, for tests and aria labels. */
export function noteText(n: Note): string {
  return n.map((p) => p.text).join('')
}

/** "Swedish, English and Russian say it differently". */
export function saysDifferently(langs: readonly string[]): string {
  return noteText(saysDifferentlyNote(langs))
}
export function saysDifferentlyNote(langs: readonly string[]): Note {
  return [{ text: editions(langs), strong: true }, { text: ` ${says(langs.length)} it differently` }]
}

/** "Swedish says 22,830" / "German, English and Russian say 25,904". value is shown as given. */
export function saysValue(langs: readonly string[], value: string): string {
  return noteText(saysValueNote(langs, value))
}
export function saysValueNote(langs: readonly string[], value: string): Note {
  return [{ text: editions(langs), strong: true }, { text: ` ${says(langs.length)} ${value}` }]
}

/** "same in the other five" / "same in the others" (count null). */
export function sameInOthers(count: number | null): string {
  return count === null ? 'same in the others' : `same in the other ${numWord(count)}`
}

/** "German same" (07: editions that still agree, named). */
export function sameIn(langs: readonly string[]): string {
  return `${editions(langs)} same`
}

/** "missing in the other four". */
export function missingInOthers(count: number): string {
  return `missing in the other ${numWord(count)}`
}

/** "Not in Russian". */
export function notIn(langs: readonly string[]): string {
  return `Not in ${editions(langs)}`
}

/** "English changed it in 2009". */
export function changedItIn(lang: string, year: string | number): string {
  return `${edition(lang)} changed it in ${year}`
}

/** "English and Swedish still agreed then" (past date view). */
export function stillAgreedThen(langs: readonly string[]): string {
  return `${editions(langs)} still agreed then`
}

/** "4 Feb 2015, Swedish changed “Soviet troops fired the shots” to “has never been settled”". */
export function changedFromTo(date: string, lang: string, from: string, to: string): string {
  return `${fmtDate(date)}, ${edition(lang)} changed “${from}” to “${to}”`
}

/** "Edit comment: “attribute the claim, sources disagree”". */
export function editComment(comment: string): string {
  return `Edit comment: “${comment}”`
}

export const REMOVED = 'Removed'
export const REMOVED_ALL = 'removed all of it'
export const REMOVED_END = 'removed the end'

/** "<b>Swedish</b> removed all of it on 3 Mar 2021" / "<b>English</b> removed “staged” on 12 Mar 2009". */
export function removedNote(lang: string, what: 'all' | 'end' | { words: string }, date: string, exact = true): Note {
  const how = what === 'all' ? REMOVED_ALL : what === 'end' ? REMOVED_END : `removed “${what.words}”`
  // A yearly snapshot only says the sentence was gone by that day, not when it went.
  const when = `${exact ? 'on' : 'by'} ${fmtDate(date)}`
  return [{ text: edition(lang), strong: true }, { text: ` ${how} ${when}` }]
}

/** "still in Finnish, German and Ukrainian". */
export function stillIn(langs: readonly string[]): string {
  return `still in ${editions(langs)}`
}

export const IN_NO_EDITION = 'In no edition'
export const DISPUTED = 'Disputed'

/** "Backed by 6 of 7 editions". */
export function backedBy(n: number, of = 7): string {
  return `Backed by ${n} of ${of} editions`
}

/** Backed only by the offline similarity guess (fake-judge-similarity): no model read the pair. */
export function likelyBackedBy(n: number, of = 7): string {
  return `Likely backed by ${n} of ${of} editions (matched by shared names and numbers, no model)`
}

/** ["Disputed", "in 3 of 7", "English removed it in 2009"]: parts of a check row head. */
export function disputedRemoved(n: number, of: number, langs: string | readonly string[], year: string | number): string[] {
  const who = typeof langs === 'string' ? edition(langs) : editions(langs)
  return [DISPUTED, `in ${n} of ${of}`, `${who} removed it in ${year}`]
}

/** "Not compared yet in Russian and Estonian": a close sentence exists, but nobody compared it with this one. */
export function notCompared(langs: readonly string[]): string {
  return `Not compared yet in ${editions(langs)}`
}

/** ["Disputed", "Swedish and Russian say otherwise"]. */
export function disputedOtherwise(langs: readonly string[]): string[] {
  return [DISPUTED, `${editions(langs)} ${says(langs.length)} otherwise`]
}

/**
 * "Of 6 statements, 1 is in no edition, 2 are disputed and 3 are backed by most editions".
 * most=false says "backed by at least one edition", for when some backed statement has only a minority behind it.
 */
export function checkSummary(s: { total: number; none: number; disputed: number; backed: number }, most = true): string {
  const be = (n: number) => (n === 1 ? 'is' : 'are')
  const parts: string[] = []
  if (s.none) parts.push(`${s.none} ${be(s.none)} in no edition`)
  if (s.disputed) parts.push(`${s.disputed} ${be(s.disputed)} disputed`)
  if (s.backed) parts.push(`${s.backed} ${be(s.backed)} backed by ${most ? 'most editions' : 'at least one edition'}`)
  const noun = s.total === 1 ? 'statement' : 'statements'
  return `Of ${s.total} ${noun}, ${joinNames(parts)}`
}

// ---------- Tabs ----------

export const TABS = {
  differences: 'Differences',
  removed: 'Removed',
  check: 'Check an AI answer',
} as const
export type TabKey = keyof typeof TABS

// ---------- Bar and footer ----------

export const WORDMARK = 'Parallax'
export const CHANGE_ARTICLE = 'Change article'
export const UNDER_THE_HOOD = 'Under the hood'
/** "Back to Winter War". */
export function backTo(title: string): string {
  return `Back to ${title}`
}
/** "← Winter War" (back link above a statement). */
export function backArrow(title: string): string {
  return `← ${title}`
}

export const FOOT = {
  licence: 'Wikipedia text CC BY-SA',
  machine: 'Translations by machine',
  affiliation: 'Not affiliated with Wikimedia',
  hood: UNDER_THE_HOOD,
} as const

// ---------- Dates and lists ----------

export const AS_OF_TODAY = 'As of today'
export const LATEST_EDIT = 'Latest edit'
/** "As of 1 Jan 2008"; without a date "Latest edit 3 Nov 2026" (the newest stored revision: data is not refreshed
 * after a load, so "today" would overstate it), or "As of today" when that day is unknown. */
export function asOf(date: string | null, latest: string | null = null): string {
  if (date) return `As of ${fmtDate(date)}`
  return latest ? `${LATEST_EDIT} ${fmtDate(latest)}` : AS_OF_TODAY
}
export const TODAY = 'Today'
export const DATE_LABEL = 'Show the article as it was on'
export const DATE_PLACEHOLDER = 'YYYY-MM-DD'
export const DATE_SHOW = 'Show'
export const DATE_INVALID = 'Write the date as YYYY-MM-DD'

/** "Showing 1 Jan 2008. Estonian and Ukrainian had no article yet". */
export function showingDate(date: string, missing: readonly string[]): string {
  const base = `Showing ${fmtDate(date)}`
  if (!missing.length) return base
  return `${base}. ${editions(missing)} had no article yet`
}
export const BACK_TO_TODAY = 'Back to today'

/** "Show 38 more". */
export function showMore(n: number): string {
  return `Show ${fmtNum(n)} more`
}

export const FIND_STATEMENT = 'Find a statement'
export const SEARCH_SHORT = 'Search'

/** "6 min". */
export function mins(seconds: number): string {
  return `${minutes(seconds)} min`
}

/** "1939 to 1940" or "1918". */
export function years(from: number | null, to: number | null): string {
  if (from === null) return ''
  return to === null || to === from ? String(from) : `${from} to ${to}`
}

// ---------- Generic errors ----------

export const ERR = {
  network: 'Could not reach Parallax. Check the connection and try again',
  notFound: 'This page does not exist',
  topicNotFound: 'This article is not loaded yet',
  generic: 'Something did not load. Try again',
  tryAgain: 'Try again',
  /** "Wikipedia asked us to slow down. Try again in 2 min". */
  rateLimited: (seconds: number) => `Wikipedia asked us to slow down. Try again in ${mins(seconds)}`,
  /** Parallax itself limits checks and new articles per visitor. */
  tooMany: (seconds: number) => `Too many requests for now. Try again in ${mins(seconds)}`,
  modelUnavailable: 'The model that reads answers is not answering. Try again later',
} as const

/** “text” in curly quotes. */
export function quote(text: string): string {
  return `“${text}”`
}
/** Cuts at a word boundary near max characters and adds "…". */
export function excerpt(text: string, max = 110): string {
  if (text.length <= max) return text
  const cut = text.slice(0, max)
  const at = cut.lastIndexOf(' ')
  return `${(at > 40 ? cut.slice(0, at) : cut).replace(/[\s.,;:]+$/, '')}…`
}

/** Placeholder line of a page stub, until its page agent builds it. */
export const STUB = 'This page is being built'
