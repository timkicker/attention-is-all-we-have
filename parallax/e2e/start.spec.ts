import { expect, test, type Locator } from '@playwright/test'
import { QID, TID, TOPIC, copy, expectFooter, path } from './support'

// Screens 01 and 02. Search asks Wikidata live, so /api/search is answered here in the contract's shape:
// one ready topic (Winter War, loaded in every seed), one that can be loaded, one without a Finnish article.
const SEARCH = {
  results: [
    { qid: QID, title: TOPIC, description: 'War between the Soviet Union and Finland', fi_title: 'Talvisota', status: 'ready', eta_s: null },
    { qid: 'Q152786', title: 'Carl Gustaf Emil Mannerheim', description: 'Finnish military leader and president', fi_title: 'C. G. E. Mannerheim', status: 'new', eta_s: 360 },
    { qid: 'Q999999', title: 'Mannerheim Example', description: 'An article with no Finnish version', fi_title: null, status: 'no_finnish', eta_s: null },
  ],
}

test('start shows the search field, the example and the prepared articles', async ({ page }) => {
  await page.goto(path.start)
  await expect(page).toHaveTitle(/Parallax/)
  await expect(page.getByTestId(TID.barLogo)).toHaveText(copy.WORDMARK)
  // wireframe 01: nothing on the right of the bar, Under the hood sits in the footer
  await expect(page.getByTestId(TID.footHood)).toHaveText(copy.UNDER_THE_HOOD)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(copy.start.HERO)
  await expect(page.getByTestId(TID.startSearch)).toBeVisible()
  await expect(page.getByTestId(TID.startPrepared).filter({ hasText: TOPIC })).toBeVisible()
  await expectFooter(page)
})

test('the example opens the Winter War comparison', async ({ page }) => {
  await page.goto(path.start)
  const open = page.getByTestId(TID.startExampleOpen)
  await expect(open).toHaveText(copy.start.OPEN_EXAMPLE)
  await open.click()
  // the example leads into the topic (its Mainila statement or the Differences tab)
  await expect(page).toHaveURL(new RegExp(`/t/${QID}(/s/fi/\\d+/[0-9a-f]{16})?$`))
})

test('search lists results with their status and links each to its page', async ({ page }) => {
  await page.route('**/api/search?*', (route) => route.fulfill({ json: SEARCH }))
  await page.goto(path.start)
  await page.getByTestId(TID.startSearch).fill('Mannerheim')
  const rows = page.getByTestId(TID.startResult)
  await expect(rows).toHaveCount(3)

  const ready = rows.filter({ hasText: TOPIC })
  await expect(ready).toHaveAttribute('data-status', 'ready')
  await expect(ready).toContainText(copy.start.READY)
  const fresh = rows.filter({ hasText: 'Carl Gustaf Emil Mannerheim' })
  await expect(fresh).toHaveAttribute('data-status', 'new')
  await expect(fresh).toContainText(copy.start.toLoad(360))
  const none = rows.filter({ hasText: 'Mannerheim Example' })
  await expect(none).toHaveAttribute('data-status', 'no_finnish')
  await expect(none).toContainText(copy.start.NO_FINNISH)
  expect(await linkOf(none)).toBeNull()

  expect(await linkOf(fresh)).toMatch(/\/t\/Q152786\/loading/)
  await ready.click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}$`))
})

test('the footer link opens Under the hood', async ({ page }) => {
  await page.goto(path.start)
  await page.getByTestId(TID.footHood).click()
  await expect(page).toHaveURL(/\/hood/)
})

// A result row is a link itself or holds one; null when it links nowhere.
async function linkOf(row: Locator): Promise<string | null> {
  return row.evaluate((e) => (e.closest('a') ?? e.querySelector('a'))?.getAttribute('href') ?? null)
}
