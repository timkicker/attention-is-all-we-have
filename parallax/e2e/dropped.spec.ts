import { expect, test } from '@playwright/test'

// PLAN demo 0:55: the ru clause "staged by the Soviet side" is dropped while de, fi and sv still state it.
test('dropped here, alive there lists the ru clause with the editions that still state it', async ({ page }) => {
  await page.goto('/dropped')
  const card = page.locator('article[data-lang="ru"]').filter({ hasText: 'инсценированный советской стороной' })
  await expect(card).toBeVisible()
  await expect(card).toContainText('Russian stopped saying it on')
  await expect(card.getByText('de: same claim')).toBeVisible()
  const last = card.getByRole('link', { name: 'Open the last revision that had it' })
  await expect(last).toHaveAttribute('href', /^https:\/\/ru\.wikipedia\.org\/w\/index\.php\?oldid=\d+$/)
  await card.getByText('Show their sentences').click()
  await expect(card.locator('[data-alive-lang="de"]')).toContainText('inszenierte')
})
