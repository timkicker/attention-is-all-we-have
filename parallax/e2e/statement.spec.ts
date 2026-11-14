import { expect, test } from '@playwright/test'
import { QID, TID, TOPIC, copy, expectFooter, path } from './support'

// Screen 06 on seed-mini: the Finnish Mainila statement. Swedish and German tell it the same way, English with
// "reported"; the original wording shows the words of each edition.
const MAINILA = { lang: 'fi', pageId: 1256, h: '8519fbaf22d33984' }

test('one statement groups the editions by wording and shows the original wording on request', async ({ page }) => {
  await page.goto(path.statement(MAINILA.lang, MAINILA.pageId, MAINILA.h))
  await expect(page.getByTestId(TID.statementBack)).toHaveText(copy.backArrow(TOPIC))
  await expect(page.getByTestId(TID.statementTitle)).toBeVisible()

  const groups = page.getByTestId(TID.statementGroup)
  await expect(groups.first()).toBeVisible()
  await expect(groups.first()).toHaveAttribute('data-langs', /^fi\b/)
  await expect(groups.first()).toContainText(copy.edition('fi'))
  const en = page.locator(`[data-testid="${TID.statementGroup}"][data-langs*="en"]`)
  await expect(en.first()).toContainText(copy.edition('en'))

  await page.getByTestId(TID.showOriginal).click()
  await expect(page.getByTestId(TID.showOriginal)).toHaveText(copy.topic.SHOW_ENGLISH)
  for (const word of ['lavasti', 'inszenierte', 'kunnat bevisas', 'reported']) {
    await expect(groups.filter({ hasText: word }).first()).toBeVisible()
  }
  await expectFooter(page)
})

test('the back link returns to the Differences tab with the date', async ({ page }) => {
  await page.goto(path.statement(MAINILA.lang, MAINILA.pageId, MAINILA.h, '2024-01-01'))
  await page.getByTestId(TID.statementBack).click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}\\?date=2024-01-01$`))
})
