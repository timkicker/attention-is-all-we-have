import { expect, test } from '@playwright/test'
import { QID, TID, TOPIC, copy, differentlyRx, expectFooter, findStatement, path } from './support'

// Screens 05 and 07 on seed-mini: the Mainila statement (English, Russian and Estonian tell it partly otherwise) and
// the Finnish dead (English says 25,904). Before 2009 Estonian had no article in seed-mini.
const MAINILA_H = '8519fbaf22d33984'
const PAST = '2008-06-01'

test('differences lists the statements other editions tell differently', async ({ page }) => {
  await page.goto(path.differences())
  await expect(page.getByTestId(TID.topicTitle)).toHaveText(TOPIC)
  await expect(page.getByTestId(TID.tabDifferences)).toContainText(copy.TABS.differences)
  await expect(page.getByTestId(TID.asOf)).toContainText(new RegExp(`^(${copy.NEWEST_VERSION} |${copy.AS_OF_TODAY})`))
  const rows = page.getByTestId(TID.diffRow)
  await expect(rows.first()).toBeVisible()

  const mainila = rows.filter({ hasText: 'Mainila' }).first()
  await expect(mainila).toContainText(differentlyRx)
  await expect(mainila).toContainText(copy.edition('en'))

  const dead = rows.filter({ hasText: '26,662' }).first()
  await expect(dead).toContainText(copy.saysValue(['en'], '25,904'))
  await expectFooter(page)
})

test('a row opens its statement', async ({ page }) => {
  await page.goto(path.differences())
  await page.getByTestId(TID.diffRow).filter({ hasText: 'Mainila' }).first().click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}/s/fi/1256/${MAINILA_H}`))
})

test('find a statement narrows the list and an empty result can be cleared', async ({ page }) => {
  await page.goto(path.differences())
  const rows = page.getByTestId(TID.diffRow)
  await expect(rows.first()).toBeVisible()
  const all = await rows.count()

  await findStatement(page, 'Mainila')
  await expect(rows.first()).toContainText('Mainila')

  await findStatement(page, 'zzqxnothing')
  await expect(page.getByTestId(TID.stateEmptyFilter)).toContainText(copy.states.noMatch('zzqxnothing', null))
  await page.getByTestId(TID.stateClearSearch).click()
  await expect(rows).toHaveCount(all)
})

test('a past date shows that day, names editions without an article and keeps the date across tabs', async ({ page }) => {
  await page.goto(path.differences(PAST))
  await expect(page.getByTestId(TID.asOf)).toContainText(copy.asOf(PAST))
  const notice = page.getByTestId(TID.noticePast)
  await expect(notice).toContainText(copy.showingDate(PAST, []))
  await expect(notice).toContainText(copy.edition('et'))

  await page.getByTestId(TID.tabRemoved).click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}/removed\\?date=${PAST}`))
  await page.getByTestId(TID.tabDifferences).click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}\\?date=${PAST}`))

  await page.getByTestId(TID.backToToday).click()
  await expect(page).toHaveURL(new RegExp(`/t/${QID}$`))
  await expect(page.getByTestId(TID.asOf)).toContainText(new RegExp(`^(${copy.NEWEST_VERSION} |${copy.AS_OF_TODAY})`))
})

test('the date control sets a date for the topic', async ({ page }) => {
  await page.goto(path.differences())
  await page.getByTestId(TID.asOf).click()
  await expect(page.getByTestId(TID.asOfPop)).toBeVisible()
  await page.getByTestId(TID.asOfInput).fill(PAST)
  await page.getByTestId(TID.asOfApply).click()
  await expect(page).toHaveURL(new RegExp(`date=${PAST}`))
  await expect(page.getByTestId(TID.noticePast)).toBeVisible()
})

test('a date that is no past day shows the newest version and leaves the address', async ({ page }) => {
  for (const bad of ['garbage', '2008-13-45', '2999-01-01']) {
    await page.goto(path.differences() + `?date=${bad}`)
    await expect(page.getByTestId(TID.asOf)).toContainText(new RegExp(`^(${copy.NEWEST_VERSION} |${copy.AS_OF_TODAY})`))
    await expect(page).toHaveURL(new RegExp(`/t/${QID}$`))
  }
})

test('on a phone the find field keeps its width beside the date button', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(path.differences())
  const field = page.getByTestId(TID.findStatement)
  await expect(field).toBeVisible()
  expect((await field.boundingBox())!.width).toBeGreaterThan(200)
})
