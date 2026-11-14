import { expect, test } from '@playwright/test'

// PLAN demo 1:15: an answer about the Mainila shots; one claim reads "en: stopped saying (2009)".
const ANSWER =
  'The Shelling of Mainila on 26 November 1939 was staged by the Soviet Union to justify the invasion of Finland. ' +
  'According to the Soviet report, four Soviet soldiers were killed in the incident. ' +
  'Finnish artillery could not reach the village of Mainila.'

test('check an answer labels each claim per edition', async ({ page }) => {
  await page.goto('/check')
  await page.getByRole('textbox', { name: 'Or paste an answer' }).fill(ANSWER)
  await page.getByRole('button', { name: 'Check this answer' }).click()
  const first = page.locator('[data-idx="0"]')
  await expect(first.locator('[data-lang="en"]')).toHaveText('en: stopped saying (2009)')
  await expect(first.locator('[data-lang="fi"]')).toHaveText('fi: says')
  await expect(page.getByText(/not found in \w\w/).first()).toBeVisible()
  await expect(page).toHaveURL(/run=[0-9a-z]{12}/)

  // the stored run replays from its URL
  await page.reload()
  await expect(page.locator('[data-idx="0"] [data-lang="en"]')).toHaveText('en: stopped saying (2009)')
})
