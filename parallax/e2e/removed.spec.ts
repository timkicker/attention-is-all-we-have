import { expect, test } from '@playwright/test'
import { QID, TID, copy, expectFooter, path } from './support'

// Screen 08 on seed-mini: two removed statements, English (the Mainila sentence, gone in the 2009 snapshot) and
// Russian (the clause "staged by the Soviet side", gone between the 2014 and 2018 snapshots).
test('removed lists what one edition removed while others still have it', async ({ page }) => {
  await page.goto(path.removed())
  await expect(page.getByTestId(TID.tabRemoved)).toContainText(copy.TABS.removed)
  const rows = page.getByTestId(TID.removedRow)
  await expect(rows).toHaveCount(2)
  const en = rows.filter({ hasText: `${copy.edition('en')} removed` })
  await expect(en).toContainText('Mainila')
  // seed-mini has yearly snapshots, so the removal is dated by year only
  await expect(en).toContainText(copy.noteText(copy.removedNote('en', 'all', '2009-12-31', false)))
  await expect(en).toContainText(copy.stillIn(['fi', 'sv', 'de', 'ru', 'et']).split(',')[0])
  await expectFooter(page)
})

test('the edition filter keeps one edition', async ({ page }) => {
  await page.goto(path.removed())
  const filter = page.getByTestId(TID.removedEdition)
  await expect(filter).toContainText(copy.removed.ANY_EDITION)
  await filter.click()
  const pop = page.getByTestId(TID.removedEditionPop)
  await pop.getByText(copy.edition('ru'), { exact: true }).click()
  const rows = page.getByTestId(TID.removedRow)
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText(`${copy.edition('ru')} removed`)
  await expect(filter).toContainText(copy.edition('ru'))
})

test('a removed row opens its statement', async ({ page }) => {
  await page.goto(path.removed())
  await page.getByTestId(TID.removedRow).first().click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}/s/`))
})
