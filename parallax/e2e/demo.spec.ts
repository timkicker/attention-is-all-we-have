import { expect, test, type APIRequestContext } from '@playwright/test'
import { FACTS, type DemoFacts } from './demo-facts'

// PLAN B11: walk the demo script of section 0 step by step and assert what the audience sees.
// make demo-check runs this file alone with demo-reporter.ts, against make demo or BASE_URL.
let f: DemoFacts
let seed = ''
let editions = 0
let mainilaRow = ''
let timeRow = ''
let deadRow = ''

// The row id of the fi sentence in `section` that contains every word, as Compare lists it at `asOf` (default today).
async function findRow(request: APIRequestContext, section: string, words: string[], asOf?: string): Promise<string> {
  const params = new URLSearchParams({ topic: 'winterwar', anchor: 'fi', section, limit: '200' })
  if (asOf) params.set('as_of', asOf)
  const body = await (await request.get(`/api/compare?${params}`)).json()
  const rows = (body.rows ?? []).filter((r: any) => words.every((w) => (r.cells.fi.text ?? '').includes(w)))
  if (rows.length !== 1) throw new Error(`${rows.length} fi rows in ${section} at ${asOf ?? 'today'} contain ${words.join(', ')}`)
  return rows[0].row_id
}

// Tagged @demo: make e2e leaves it out, since its facts need a full seed (not seed-mini).
test.describe('demo script @demo', () => {
  test.beforeAll(async ({ request }) => {
    const health = await (await request.get('/api/health')).json()
    seed = health.seed
    if (!FACTS[seed]) throw new Error(`no demo facts for seed ${seed}; load seed ${Object.keys(FACTS).join(', ')}`)
    f = FACTS[seed]
    const topics = (await (await request.get('/api/topics')).json()).topics
    editions = topics.find((t: any) => t.topic_id === 'winterwar').editions.length
    mainilaRow = await findRow(request, f.mainila.section, f.mainila.words)
    timeRow = await findRow(request, f.mainila.section, f.mainila.words, f.enFlip.before)
    deadRow = await findRow(request, f.dead.section, [f.dead.fi])
  })

  test('0:00 title: the wordmark Parallax', async ({ page }) => {
    await page.goto('/compare')
    await expect(page).toHaveTitle(/Parallax/)
    await expect(page.locator('header').getByText('Parallax', { exact: true }).first()).toBeVisible()
  })

  test('0:08 compare: the Mainila row in every edition, terms and numbers that differ', async ({ page }) => {
    await page.goto(`/compare?section=${encodeURIComponent(f.mainila.section)}`)
    const row = page.locator(`[data-row="${mainilaRow}"]`)
    await expect(row).toBeVisible()
    await expect(row.locator('[data-lang]')).toHaveCount(editions)
    for (const [lang, term] of Object.entries(f.mainila.terms)) {
      await expect(row.locator(`[data-lang="${lang}"]`)).toContainText(term)
    }
    await expect(row.getByText(f.mainila.chip).first()).toBeVisible()

    await page.goto(`/compare?section=${encodeURIComponent(f.dead.section)}`)
    const dead = page.locator(`[data-row="${deadRow}"]`)
    await expect(dead.locator('[data-lang="fi"]')).toContainText(f.dead.fi)
    for (const lang of f.dead.differs) {
      await expect(dead.locator(`[data-lang="${lang}"]`)).toContainText('number differs')
    }
  })

  test('0:30 time: the en Mainila sentence changes between two dates, with life bars', async ({ page }) => {
    const en = page.locator('.claim-timeline [data-focus-lang="en"]')
    await page.goto(`/time?claim=${timeRow}&as_of=${f.enFlip.before}`)
    await expect(en).toContainText(f.enFlip.beforeText)
    await page.goto(`/time?claim=${timeRow}&as_of=${f.enFlip.after}`)
    await expect(en).toContainText(f.enFlip.afterText)
    await expect(en).not.toContainText('staged')
    await expect(page.locator('.life-bars [data-lang="en"] .life-bars__bar').first()).toBeVisible()
    if (f.enFlip.comment) await expect(page.locator(`[title*="${f.enFlip.comment}"]`).first()).toBeAttached()
  })

  test('0:55 dropped: the ru clause with its date while other editions still state it', async ({ page }) => {
    await page.goto('/dropped')
    await page.locator('.dropped__field', { hasText: 'Edition that dropped it' }).getByRole('combobox').click()
    await page.getByRole('option', { name: 'Russian (ru)' }).click()
    // longest stated first: the clause can sit a few pages down, so page on as a reader would
    const card = page.locator('article[data-lang="ru"]').filter({ hasText: f.ruDropped.text })
    const more = page.getByRole('button', { name: /^Show \d+ more of/ })
    await expect(page.locator('article[data-lang="ru"]').first()).toBeVisible()
    for (let i = 0; i < 10 && !(await card.count()) && (await more.count()); i++) {
      const before = await page.locator('article[data-lang="ru"]').count()
      await more.click()
      await expect(page.locator('article[data-lang="ru"]')).not.toHaveCount(before)
    }
    await expect(card).toContainText(`Russian stopped saying it on ${f.ruDropped.date}`)
    await expect(card.getByText(f.ruDropped.alive)).toBeVisible()
    await expect(card.getByRole('link', { name: 'Open the last revision that had it' })).toHaveAttribute(
      'href',
      `https://ru.wikipedia.org/w/index.php?oldid=${f.ruDropped.oldid}`,
    )
    if (f.fiScale) await expect(page.getByTestId('fi-scale')).toContainText('sentence lives')
  })

  test('1:15 check: a recorded answer with its model and a stopped saying chip', async ({ page, request }) => {
    const runs = (await (await request.get('/api/check/recorded')).json()).runs
    expect(runs.length, 'no recorded answer; make demo records one').toBeGreaterThan(0)
    // the script shows the answer about the Mainila shots
    const run = runs.find((r: any) => (r.question ?? '').includes('Mainila')) ?? runs[0]
    await page.goto(`/check?run=${run.run_id}`)
    await expect(page.getByText(`Recorded answer from ${run.answer_model}`)).toBeVisible()
    await expect(page.getByText(/^en: stopped saying \(\d{4}\)$/).first()).toBeVisible()
    await expect(page.getByText(/not found in \w\w/).first()).toBeVisible()
  })

  test('1:35 under the hood: one statement with AS OF and the vector distance, ms and rows', async ({ page }) => {
    await page.goto('/hood')
    await expect(page.getByTestId('hood-timing')).toContainText(/\d+(\.\d)? ms, [\d,]+ rows/)
    const both = page.getByTestId('sql-statement').filter({ hasText: 'FOR SYSTEM_TIME AS OF' }).filter({ hasText: 'VEC_DISTANCE_COSINE' })
    await expect(both.first()).toBeVisible()
    await expect(page.getByTestId('hood-stats')).toBeVisible()
  })

  test('1:50 footer and an Open on fi.wikipedia link', async ({ page }) => {
    await page.goto(`/compare?section=${encodeURIComponent(f.mainila.section)}`)
    await expect(
      page.getByText(
        'Independent hackathon project. Not affiliated with or endorsed by the Wikimedia Foundation. Wikipedia is a trademark of the Wikimedia Foundation.',
      ),
    ).toBeVisible()
    await expect(page.getByText('Evidence, not edits.')).toBeVisible()
    const open = page.locator(`[data-row="${mainilaRow}"] [data-lang="fi"]`).getByRole('link', { name: 'Open on fi.wikipedia' })
    await expect(open).toHaveAttribute('href', /^https:\/\/fi\.wikipedia\.org\/w\/index\.php\?oldid=\d+/)
    await expect(page.getByRole('button', { name: /edit/i })).toHaveCount(0)
  })
})
