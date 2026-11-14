import { expect, test } from '@playwright/test'

test('ask quotes every edition and writes nothing of its own', async ({ page }) => {
  await page.goto('/ask')
  await page.getByLabel('Question').fill('Who fired the shots at Mainila?')
  await page.getByRole('button', { name: 'Find quotes' }).click()
  await expect(page).toHaveURL(/q=Who\+fired/)
  const editions = page.getByTestId('ask-edition')
  await expect(editions.first()).toBeVisible()
  expect(await editions.count()).toBeGreaterThanOrEqual(6)
  for (const lang of ['fi', 'sv', 'de', 'en', 'ru', 'et']) {
    const link = page.locator(`[data-lang="${lang}"] a`).first()
    await expect(link).toHaveText(`Open on ${lang}.wikipedia`)
    await expect(link).toHaveAttribute('href', new RegExp(`^https://${lang}\\.wikipedia\\.org/w/index\\.php\\?oldid=\\d+$`))
  }
  await expect(page.getByText('writes nothing of its own')).toBeVisible()
  await expect(page.getByTestId('sql-panel')).toContainText('GET /api/ask')
})
