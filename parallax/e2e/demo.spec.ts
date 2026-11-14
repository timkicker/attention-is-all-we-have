import { expect, test } from '@playwright/test'
import { FACTS, type DemoFacts } from './demo-facts'
import { QID, TID, copy, differentlyRx, escapeRx, expectFooter, findStatement, path, showMoreUntil } from './support'

// PLAN B11: walk the demo script of section 0 on the new screens and assert what the audience sees.
// make demo-check runs this file alone with demo-reporter.ts, against make demo or BASE_URL.
let f: DemoFacts

// Tagged @demo: make e2e leaves it out, since its facts need a full seed (not seed-mini).
test.describe('demo script @demo', () => {
  test.beforeAll(async ({ request }) => {
    const seed = (await (await request.get('/api/health')).json()).seed
    if (!FACTS[seed]) throw new Error(`no demo facts for seed ${seed}; load seed ${Object.keys(FACTS).join(', ')}`)
    f = FACTS[seed]
  })

  test('0:00 start: the wordmark and the Winter War example', async ({ page }) => {
    await page.goto(path.start)
    await expect(page).toHaveTitle(/Parallax/)
    await expect(page.getByTestId(TID.barLogo)).toHaveText(copy.WORDMARK)
    await page.getByTestId(TID.startExampleOpen).click()
    await expect(page).toHaveURL(new RegExp(`/t/${QID}(/s/fi/\\d+/[0-9a-f]{16})?$`))
  })

  test('0:08 differences: Mainila told differently, the Finnish dead with other numbers', async ({ page }) => {
    await page.goto(path.differences())
    const rows = page.getByTestId(TID.diffRow)
    await findStatement(page, f.mainila.find)
    const mainila = rows.filter({ hasText: f.mainila.words })
    await expect(mainila.first()).toBeVisible()
    await expect(mainila.first()).toContainText(differentlyRx)

    await findStatement(page, f.dead.find)
    const dead = rows.filter({ hasText: f.dead.fi }).filter({ hasText: f.dead.other })
    await expect(dead.first()).toBeVisible()
    for (const lang of f.dead.differs) await expect(dead.first()).toContainText(copy.edition(lang))
  })

  test('0:20 statement: each edition in its own words', async ({ page }) => {
    await page.goto(path.differences())
    await findStatement(page, f.mainila.find)
    await page.getByTestId(TID.diffRow).filter({ hasText: f.mainila.words }).first().click()
    await expect(page).toHaveURL(new RegExp(`/t/${QID}/s/fi/`))
    await page.getByTestId(TID.showOriginal).click()
    const groups = page.getByTestId(TID.statementGroup)
    for (const [lang, words] of Object.entries(f.mainila.originals)) {
      const g = page.locator(`[data-testid="${TID.statementGroup}"][data-langs*="${lang}"]`)
      await expect(g.filter({ hasText: words }).first(), `${lang} says ${words}`).toBeVisible()
    }
    await expect(groups.first()).toContainText(copy.edition('fi'))
  })

  test('0:30 a past date: English said staged before 2009, a border incident after', async ({ page }) => {
    const { pageId, h, before, after, beforeText, afterText, year } = f.enFlip
    await page.goto(path.differences(before))
    await expect(page.getByTestId(TID.noticePast)).toContainText(copy.showingDate(before, []))

    await page.goto(path.statement('fi', pageId, h, before))
    await page.getByTestId(TID.showOriginal).click()
    await expect(page.locator('main')).toContainText(beforeText)

    await page.goto(path.statement('fi', pageId, h, after))
    await page.getByTestId(TID.showOriginal).click()
    const en = page.locator(`[data-testid="${TID.statementGroup}"][data-langs*="en"]`)
    await expect(en.first()).toContainText(afterText)
    await expect(en.first()).not.toContainText('staged')
    await expect(page.getByTestId(TID.changeRow).filter({ hasText: copy.edition('en') }).filter({ hasText: String(year) }).first()).toBeVisible()
  })

  test('0:55 removed: Russian removed the staged clause while German still has it', async ({ page }) => {
    const { words, date, alive, oldid } = f.ruDropped
    await page.goto(path.removed())
    await page.getByTestId(TID.removedEdition).click()
    await page.getByTestId(TID.removedEditionPop).getByText(copy.edition('ru'), { exact: true }).click()
    await findStatement(page, 'Mainila')
    const rows = page.getByTestId(TID.removedRow)
    const row = rows.filter({ hasText: words })
    await showMoreUntil(page, rows, row)
    await expect(row.first()).toContainText(new RegExp(`${copy.edition('ru')} removed .* on ${escapeRx(copy.fmtDate(date))}`))
    await expect(row.first()).toContainText(copy.edition(alive))

    await row.first().click()
    await expect(page).toHaveURL(new RegExp(`/t/${QID}/s/ru/`))
    await page.getByTestId(TID.showOriginal).click()
    await expect(page.locator(`a[href*="oldid=${oldid}"]`).first()).toBeAttached()
  })

  test('1:15 check: a recorded answer about Mainila, its statements backed or disputed', async ({ page, request }) => {
    const runs = (await (await request.get('/api/check/recorded')).json()).runs
    expect(runs.length, 'no recorded answer; make demo records one').toBeGreaterThan(0)
    await page.goto(path.check())
    // the script shows the recorded answer about the Mainila shots (the first one the page offers)
    const link = page.getByTestId(TID.checkRecorded).filter({ hasText: 'Mainila' }).first()
    const runId = ((await link.getAttribute('href')) ?? '').split('/').pop()!.split('?')[0]
    const run = runs.find((r: any) => r.run_id === runId)
    expect(run, `recorded link ${runId} is a recorded run`).toBeTruthy()
    await link.click()
    await expect(page).toHaveURL(new RegExp(`/t/${QID}/check/${runId}`))
    await expect(page.getByTestId(TID.checkMeta)).toBeVisible()
    if (run.answer_date) await expect(page.getByTestId(TID.checkMeta)).toContainText(copy.fmtDate(run.answer_date))
    const rows = page.getByTestId(TID.checkRow)
    await expect(rows.first()).toBeVisible()
    await expect(page.getByTestId(TID.checkSummary)).toContainText(/^Of \d+ statements?/)
    await expect(page.locator(`[data-testid="${TID.checkRow}"][data-verdict="disputed"]`).first()).toBeVisible()
    await expect(page.locator(`[data-testid="${TID.checkRow}"][data-verdict="backed"]`).first()).toBeVisible()
  })

  test('1:35 under the hood: the one query with AS OF and the vector distance, its time', async ({ page }) => {
    await page.goto(path.hood(QID))
    const sql = page.getByTestId(TID.hoodQuery)
    await expect(sql).toContainText('FOR SYSTEM_TIME')
    await expect(sql).toContainText('VEC_DISTANCE_COSINE')
    await expect(page.locator(`[data-testid="${TID.hoodNumber}"][data-key="query_ms"]`)).toContainText(/\d+ ms/)
    await expect(page.locator(`[data-testid="${TID.hoodNumber}"][data-key="versions"]`)).toContainText(/\d/)
  })

  test('1:50 footer and the Finnish sentence on fi.wikipedia', async ({ page }) => {
    await page.goto(path.differences())
    await expectFooter(page)
    await findStatement(page, f.mainila.find)
    await page.getByTestId(TID.diffRow).filter({ hasText: f.mainila.words }).first().click()
    await page.getByTestId(TID.showOriginal).click()
    await expect(page.locator('a[href^="https://fi.wikipedia.org/w/index.php?oldid="]').first()).toBeAttached()
    await expectFooter(page)
  })
})
