// Words of Under the hood (11). Owner: P4.
// The only page where technical words (embedding, vector, distance, model) are allowed.

import { fmtNum } from '../format'

export const TITLE = 'Under the hood'
export const SUB = 'How Parallax lines up seven editions, for anyone who wants the technical part'
export const MATCHED_H = 'How statements are matched'
export const MATCHED_P1 = 'Every version of every edition is stored in MariaDB with system versioning, so any past day can be read back exactly as it was.'
export const MATCHED_P2 = 'Each Finnish statement gets an embedding. Vector search finds candidate matches in the other editions, then a model checks each pair and decides: same, said differently, or not there.'
export const QUERY_H = 'The query'
export const QUERY_P = 'The Differences list reads one past day and finds the five closest statements across all editions'
export const NUMBERS_H = 'Numbers'
/** "Versions stored for Winter War". */
export function versionsFor(topic: string): string {
  return `Versions stored for ${topic}`
}
export const TOP1 = 'Top-1 recall'
export const TOP5 = 'Top-5 recall'
export const QUERY_MS = 'Differences list query'
/** "62 ms". */
export function ms(n: number): string {
  return `${fmtNum(Math.round(n))} ms`
}
/** 0.57 -> "0.57". */
export function recall(n: number): string {
  return n.toFixed(2)
}
export const NOT_MEASURED = 'Not measured'
export const LIMITS_H = 'Limits'
export const LIMIT_TRANSLATION = 'English lines are machine translations, so wording differences can come from the translation'
/** "The model misses some matches. Top-1 recall is 0.57, so check the source edition before quoting". */
export function limitRecall(top1: number): string {
  return `The model misses some matches. Top-1 recall is ${recall(top1)}, so check the source edition before quoting`
}
export const LIMIT_SCOPE = 'Only seven editions, and only articles that have a Finnish version'
