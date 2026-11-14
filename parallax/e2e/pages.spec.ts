import { expect, test } from '@playwright/test'
import { TID, expectFooter, path } from './support'

// Every route at phone width: the footer, no edit control and no horizontal scroll (BRIEF: works at 390).
const ROUTES = [path.start, path.differences(), path.removed(), path.check(), path.hood()]

test.use({ viewport: { width: 390, height: 844 } })

for (const route of ROUTES) {
  test(`${route} fits 390 px and carries the footer`, async ({ page }) => {
    await page.goto(route)
    await expect(page.getByTestId(TID.bar)).toBeVisible()
    await expect(page.getByTestId(TID.stateSkeleton)).toHaveCount(0)
    await expectFooter(page)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow, 'horizontal overflow in px').toBeLessThanOrEqual(0)
  })
}
