import { expect, test } from '@playwright/test'
import { QID, TID, copy, expectFooter, path } from './support'

// Screens 09 and 10 on seed-mini with the fake engine: the answer about the Mainila shots that the engine fixtures
// split into three statements. The first one is backed or disputed by the editions, never in no edition.
const ANSWER =
  'The Shelling of Mainila on 26 November 1939 was staged by the Soviet Union to justify the invasion of Finland. ' +
  'According to the Soviet report, four Soviet soldiers were killed in the incident. ' +
  'Finnish artillery could not reach the village of Mainila.'

test('check an answer gives each statement a finding and replays from its URL', async ({ page }) => {
  await page.goto(path.check())
  await expect(page.getByTestId(TID.tabCheck)).toContainText(copy.TABS.check)
  await page.getByTestId(TID.checkInput).fill(ANSWER)
  await page.getByTestId(TID.checkSubmit).click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}/check/[0-9a-z]{12}`))

  const rows = page.getByTestId(TID.checkRow)
  await expect(rows).toHaveCount(3)
  await expect(rows.filter({ hasText: 'staged by the Soviet Union' })).toHaveAttribute('data-verdict', /^(backed|disputed)$/)
  await expect(page.getByTestId(TID.checkSummary)).toContainText(`Of 3 statements`)
  await expect(page.getByTestId(TID.checkAnswer)).toContainText('Shelling of Mainila')
  await expectFooter(page)

  const verdicts = await rows.evaluateAll((els) => els.map((e) => e.getAttribute('data-verdict')))
  await page.reload()
  await expect(rows).toHaveCount(3)
  expect(await rows.evaluateAll((els) => els.map((e) => e.getAttribute('data-verdict')))).toEqual(verdicts)

  await page.getByTestId(TID.checkAgain).click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}/check$`))
})

test('an empty answer is not sent', async ({ page }) => {
  await page.goto(path.check())
  await page.getByTestId(TID.checkSubmit).click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}/check$`))
})
