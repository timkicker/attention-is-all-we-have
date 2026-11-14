import { expect, test } from '@playwright/test'

// PLAN B7 done check: Hood shows one statement with both FOR SYSTEM_TIME AS OF and VEC_DISTANCE_COSINE.
test('under the hood shows the one statement with AS OF and the vector distance', async ({ page }) => {
  await page.goto('/hood')
  await expect(page.getByTestId('hood-timing')).toContainText(/\d+(\.\d)? ms, [\d,]+ rows/)
  const statements = page.getByTestId('sql-statement')
  const both = statements.filter({ hasText: 'FOR SYSTEM_TIME AS OF' }).filter({ hasText: 'VEC_DISTANCE_COSINE' })
  await expect(both.first()).toBeVisible()
  await expect(page.getByTestId('hood-stats')).toContainText('Sentence lives')
})

test('every data view has its SQL panel', async ({ page }) => {
  for (const view of ['compare', 'dropped']) {
    await page.goto(`/${view}`)
    const panel = page.getByTestId('sql-panel')
    await expect(panel).toContainText(`GET /api/${view}`)
    await panel.locator('summary').click()
    await expect(panel.getByTestId('sql-statement').filter({ hasText: 'FOR SYSTEM_TIME' }).first()).toBeVisible()
  }
})
