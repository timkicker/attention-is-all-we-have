import { expect, test } from '@playwright/test'
import { sources7 } from '../web/tests/sources7'

// PLAN B8 done check: Playwright sees 7 bars. Real data comes with seed v3 (A14); before that the API answer is
// replaced by seven editions in the contract's shape, and the live API is checked for its empty state.
test('sources draws one bar per edition', async ({ page }) => {
  if (process.env.E2E_SEED !== 'v3')
    await page.route('**/api/sources?*', (route) => route.fulfill({ json: sources7 }))
  await page.goto('/sources')
  await expect(page.getByTestId('isbn-bar')).toHaveCount(7)
  await expect(page.locator('[data-testid="sources-edition"]').first()).toContainText('cites mostly')
})

test('sources answers from the live API', async ({ page }) => {
  test.skip(process.env.E2E_SEED === 'v3', 'covered by the first test on seed v3')
  await page.goto('/sources')
  await expect(page.getByText('No reference counts for this date')).toBeVisible()
})
