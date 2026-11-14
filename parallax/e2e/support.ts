// Shared bits of the specs. Test ids and visible words come from the web sources, so a word lives in one place:
// a spec that asserts a sentence builds it with the same copy function the page uses.
import { expect, type Locator, type Page } from '@playwright/test'
import * as copy from '../web/src/lib/copy'
import { TID } from '../web/src/lib/testids'

export { copy, TID }

// Winter War, the topic every seed holds.
export const QID = 'Q134949'
export const TOPIC = 'Winter War'

export const path = {
  start: '/',
  loading: (qid = QID) => `/t/${qid}/loading`,
  differences: (date?: string, qid = QID) => `/t/${qid}${date ? `?date=${date}` : ''}`,
  statement: (lang: string, pageId: number | string, h: string, date?: string, qid = QID) =>
    `/t/${qid}/s/${lang}/${pageId}/${h}${date ? `?date=${date}` : ''}`,
  removed: (date?: string, qid = QID) => `/t/${qid}/removed${date ? `?date=${date}` : ''}`,
  check: (qid = QID) => `/t/${qid}/check`,
  checkRun: (runId: string, qid = QID) => `/t/${qid}/check/${runId}`,
  hood: (from?: string) => `/hood${from ? `?from=${from}` : ''}`,
}

export const byTid = (page: Page | Locator, id: string) => page.getByTestId(id)

/** " it differently": the tail of copy.saysDifferently, whatever the edition names before it. */
export const DIFFERENTLY = copy.saysDifferently(['fi']).slice(`${copy.edition('fi')} says`.length)

/** Matches "<names> says|say it differently" for any edition names. */
export const differentlyRx = new RegExp(`\\b(says|say)${escapeRx(DIFFERENTLY)}`)

export function escapeRx(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** The footer line every page carries, and no control that could edit Wikipedia. */
export async function expectFooter(page: Page) {
  const foot = page.getByTestId(TID.foot)
  await expect(foot).toBeVisible()
  await expect(foot).toContainText(copy.FOOT.affiliation)
  await expect(foot).toContainText(copy.FOOT.licence)
  await expect(page.getByRole('button', { name: /\bedit\b/i })).toHaveCount(0)
}

/** Clicks "Show N more" until `target` appears or the button is gone (at most `rounds` times). */
export async function showMoreUntil(page: Page, rows: Locator, target: Locator, rounds = 20) {
  const more = page.getByTestId(TID.showMore)
  await expect(rows.first()).toBeVisible()
  for (let i = 0; i < rounds && !(await target.count()) && (await more.count()); i++) {
    const before = await rows.count()
    await more.click()
    await expect(rows).not.toHaveCount(before)
  }
}

/** Types into "Find a statement" (the test id sits on the input or on its field) and submits. */
export async function findStatement(page: Page, q: string) {
  const id = TID.findStatement
  const input = page.locator(`input[data-testid="${id}"], [data-testid="${id}"] input`).first()
  await input.fill(q)
  await input.press('Enter')
  // the field also searches on its own after a short pause; let that reload finish before reading or paging the list
  await expect(page).toHaveURL(new RegExp(`[?&]q=${encodeURIComponent(q).replace(/%20/g, '\\+')}`))
  await page.waitForLoadState('networkidle')
}
