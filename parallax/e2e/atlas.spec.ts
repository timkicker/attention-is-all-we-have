import { expect, test } from '@playwright/test'
import { atlas5 } from '../web/tests/atlas5'

// Real atlas data comes with seed v3 (A13); before that the API answer is replaced by five topics in the contract's shape.
test('atlas lists topics, sorts by a distance and links Winter War to Compare', async ({ page }) => {
  if (process.env.E2E_SEED !== 'v3') await page.route('**/api/atlas?*', (route) => route.fulfill({ json: atlas5 }))
  await page.goto('/atlas')
  await expect(page.getByTestId('atlas-row').first()).toBeVisible()
  const sorted = page.waitForRequest((r) => r.url().includes('/api/atlas?sort=fi_sv'))
  await page.getByTestId('atlas-sort-fi_sv').click()
  await sorted
  await page.getByRole('link', { name: 'Winter War' }).click()
  await expect(page).toHaveURL(/\/compare/)
})

test('atlas answers from the live API', async ({ page }) => {
  test.skip(process.env.E2E_SEED === 'v3', 'covered by the first test on seed v3')
  await page.goto('/atlas')
  await expect(page.getByText('The atlas is not loaded yet')).toBeVisible()
  await expect(page.getByTestId('sql-panel')).toContainText('GET /api/atlas')
})
