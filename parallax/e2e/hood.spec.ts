import { expect, test } from '@playwright/test'
import { QID, TID, TOPIC, copy, path } from './support'

// Screen 11: how statements are matched, the one query with AS OF and the vector distance, numbers and limits.
test('under the hood shows the query with AS OF and the vector distance', async ({ page }) => {
  await page.goto(path.hood())
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(copy.hood.TITLE)
  await expect(page.getByTestId(TID.hoodSection)).toHaveCount(4)
  for (const s of ['matched', 'query', 'numbers', 'limits'])
    await expect(page.locator(`[data-testid="${TID.hoodSection}"][data-section="${s}"]`)).toBeVisible()
  const sql = page.getByTestId(TID.hoodQuery)
  await expect(sql).toContainText('FOR SYSTEM_TIME')
  await expect(sql).toContainText('VEC_DISTANCE_COSINE')
  await expect(page.getByTestId(TID.hoodNumber)).toHaveCount(4)
  await expect(page.getByTestId(TID.foot)).toContainText(copy.FOOT.affiliation)
})

test('coming from a topic the bar leads back to it', async ({ page }) => {
  await page.goto(path.hood(QID))
  const back = page.getByTestId(TID.barLink)
  await expect(back).toHaveText(copy.backTo(TOPIC))
  await back.click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}`))
})
