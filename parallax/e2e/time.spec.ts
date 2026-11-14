import { expect, test, type Page } from '@playwright/test'

// PLAN B4: moving the slider from 2008 to 2012 changes the en cell of the Mainila claim.
const MAINILA = 'fi:1256:8519fbaf22d33984'

async function slideTo(page: Page, label: string) {
  const slider = page.getByRole('slider', { name: 'Date to cut every edition at' })
  await slider.focus()
  for (let i = 0; i < 40; i++) {
    if ((await page.getByTestId('slider-date').textContent()) === label) return
    await slider.press('ArrowRight')
  }
  throw new Error(`slider never reached ${label}`)
}

test('the slider moves every edition to the same instant', async ({ page }) => {
  await page.goto(`/time?claim=${MAINILA}&as_of=2008-01-01`)
  const en = page.locator('.claim-timeline [data-focus-lang="en"]')
  await expect(en).toContainText('the Soviets staged the Shelling of Mainila')
  await expect(page.getByTestId('slider-date')).toHaveText('1 Jan 2008')

  const refetch = page.waitForRequest((r) => r.url().includes('/api/compare') && r.url().includes('as_of=2012-01-01'))
  await slideTo(page, '1 Jan 2012')
  await refetch
  await expect(page).toHaveURL(/as_of=2012-01-01/)
  await expect(en).not.toContainText('staged')

  await slideTo(page, '1 Jan 2018')
  await expect(en).toContainText('an incident was reported')
  await expect(page.locator('.life-bars [data-lang="en"] .life-bars__bar').first()).toBeVisible()
})

test('a click on a Compare cell opens its timeline drawer', async ({ page }) => {
  await page.goto('/compare?section=Osapuolten%20tappiot')
  const cell = page.locator('[data-row] [data-lang="en"][role="button"]').first()
  await cell.click()
  const drawer = page.getByRole('dialog', { name: 'Timeline of the sentence' })
  await expect(drawer).toBeVisible()
  await expect(drawer.locator('.life-bars')).toBeVisible()
  await expect(page).toHaveURL(/claim=en%3A/)
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
})

test('every page carries the footer and no edit control', async ({ page }) => {
  for (const view of ['compare', 'time', 'dropped']) {
    await page.goto(`/${view}`)
    await expect(page.getByText('Independent hackathon project. Not affiliated with or endorsed by')).toBeVisible()
    await expect(page.getByRole('button', { name: /edit/i })).toHaveCount(0)
  }
})
