// Full-page screenshots at 1280 and 390.
//   node scripts/shoot.mjs <baseUrl> <outDir> name=path [name=path ...]
//   node scripts/shoot.mjs <baseUrl> <outDir> --routes scripts/routes.json [name ...]
// Writes <outDir>/<name>-1280.png and <name>-390.png. A routes.json entry may carry
// "type": "text" (typed into the first input, then waits) and "click": "<css selector>".
// Prints, per shot, any horizontal overflow and any text under 13px.
import { readFileSync, mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const [base, out, ...rest] = process.argv.slice(2)
if (!base || !out) {
  console.error('usage: shoot.mjs <baseUrl> <outDir> (name=path ... | --routes file [name ...])')
  process.exit(2)
}
let shots = []
if (rest[0] === '--routes') {
  const table = JSON.parse(readFileSync(rest[1], 'utf8'))
  const only = new Set(rest.slice(2))
  shots = Object.entries(table)
    .filter(([n]) => !only.size || only.has(n))
    .map(([name, v]) => (typeof v === 'string' ? { name, path: v } : { name, ...v }))
} else {
  shots = rest.map((s) => {
    const i = s.indexOf('=')
    return { name: s.slice(0, i), path: s.slice(i + 1) }
  })
}
mkdirSync(out, { recursive: true })
const browser = await chromium.launch()
let problems = 0
for (const width of [1280, 390]) {
  const page = await browser.newPage({ viewport: { width, height: 800 }, deviceScaleFactor: 1 })
  for (const s of shots) {
    await page.goto(new URL(s.path, base).href, { waitUntil: 'networkidle' })
    if (s.click) await page.click(s.click)
    if (s.type) {
      const input = page.locator('input').first()
      if (await input.count()) {
        await input.fill(s.type)
        await page.waitForTimeout(400)
      } else console.log(`${s.name}: no input to type into yet`)
    }
    await page.evaluate(() => document.fonts.ready)
    await page.waitForTimeout(150)
    const report = await page.evaluate(() => {
      const over = document.documentElement.scrollWidth - window.innerWidth
      const small = []
      for (const el of document.querySelectorAll('body *')) {
        if (!el.childNodes.length || ![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue
        const r = el.getBoundingClientRect()
        if (!r.width) continue
        const fs = parseFloat(getComputedStyle(el).fontSize)
        if (fs < 13) small.push(`${el.tagName.toLowerCase()} ${fs}px "${el.textContent.trim().slice(0, 30)}"`)
      }
      const overlay = !!document.querySelector('vite-error-overlay')
      return { over, small, overlay }
    })
    const file = `${out}/${s.name}-${width}.png`
    await page.screenshot({ path: file, fullPage: true })
    const notes = []
    if (report.overlay) notes.push('VITE ERROR OVERLAY (page does not compile)')
    if (report.over > 0) notes.push(`overflow ${report.over}px`)
    if (report.small.length) notes.push(`small text: ${report.small.slice(0, 3).join('; ')}`)
    if (notes.length) problems++
    console.log(`${file}${notes.length ? '  ' + notes.join(' | ') : ''}`)
  }
  await page.close()
}
await browser.close()
console.log(`shoot: ${shots.length * 2} shots, ${problems} with problems`)
