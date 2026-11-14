import { expect, test, type Page } from '@playwright/test'
import { QID, TID, copy, expectFooter, path } from './support'

// Screens 03 and 04. A real ingest would read Wikipedia, so a running job is answered here in the contract's shape.
// The loaded topic (Winter War) is asked live: the API reports it done.
const LANGS = ['fi', 'sv', 'de', 'en', 'ru', 'et', 'uk'] as const
const NEW_QID = 'Q152786'

function job(states: Record<string, [string, number]>, state: string, etaS: number | null) {
  return {
    job_id: NEW_QID,
    qid: NEW_QID,
    topic_id: 'q152786',
    title: 'Carl Gustaf Emil Mannerheim',
    state,
    eta_s: etaS,
    since: null,
    editions: LANGS.map((lang) => ({
      lang,
      state: states[lang][0],
      pct: states[lang][1],
      error: states[lang][0] === 'failed' ? 'rate_limited' : null,
      retry_at: states[lang][0] === 'failed' ? new Date(Date.now() + 120_000).toISOString() : null,
    })),
  }
}

const RUNNING = job(
  { fi: ['done', 100], sv: ['done', 100], de: ['running', 91], en: ['running', 28], ru: ['waiting', 0], et: ['waiting', 0], uk: ['waiting', 0] },
  'running',
  240,
)
const USABLE = job(
  { fi: ['done', 100], sv: ['done', 100], de: ['done', 100], en: ['running', 71], ru: ['failed', 20], et: ['done', 100], uk: ['waiting', 0] },
  'usable',
  120,
)

async function answer(page: Page, body: object) {
  await page.route(`**/api/ingest/${NEW_QID}`, (route) => route.fulfill({ json: body }))
  await page.route('**/api/ingest', (route) => route.fulfill({ status: 202, json: body }))
}

test('a running ingest shows every edition with its progress and the time left', async ({ page }) => {
  await answer(page, RUNNING)
  await page.goto(path.loading(NEW_QID))
  await expect(page.getByTestId(TID.ingestTitle)).toHaveText('Carl Gustaf Emil Mannerheim')
  await expect(page.getByTestId(TID.ingestEta)).toHaveText(copy.start.left(240))
  const rows = page.getByTestId(TID.ingestEdition)
  await expect(rows).toHaveCount(7)
  await expect(rows.nth(0)).toHaveAttribute('data-lang', 'fi')
  await expect(rows.nth(0)).toContainText(copy.edition('fi'))
  await expect(rows.nth(0)).toContainText(copy.start.DONE)
  await expect(rows.nth(2)).toContainText(copy.start.pct(91))
  await expect(rows.nth(4)).toHaveAttribute('data-state', 'waiting')
  await expect(rows.nth(4)).toContainText(copy.start.WAITING)
  await expect(page.getByTestId(TID.ingestOpen)).toHaveCount(0)
  await expectFooter(page)
})

test('once usable the ready editions can be compared and a failed edition says why', async ({ page }) => {
  await answer(page, USABLE)
  await page.goto(path.loading(NEW_QID))
  await expect(page.getByTestId(TID.ingestOpen)).toHaveText(copy.start.compareReady(4))
  await expect(page.getByTestId(TID.ingestEdition).filter({ hasText: copy.edition('ru') })).toHaveAttribute('data-state', 'failed')
  await expect(page.getByTestId(TID.ingestOpen)).toHaveAttribute('href', new RegExp(`/t/${NEW_QID}$`))
})

test('a loaded topic is done and opens its comparison', async ({ page }) => {
  await page.goto(path.loading(QID))
  // a finished job may forward straight to the topic; otherwise the open button leads there
  const open = page.getByTestId(TID.ingestOpen)
  await expect(open.or(page.getByTestId(TID.topicTitle))).toBeVisible()
  if (await open.isVisible()) await open.click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}$`))
})
