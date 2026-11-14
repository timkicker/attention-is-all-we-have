import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import timeline from '../../../contract/examples/timeline.json'
import ClaimTimeline from './ClaimTimeline.vue'
import LifeBars from './LifeBars.vue'
import type { Life } from '../api'
import { FORBIDDEN } from '../../tests/forbidden'

const KEY = 'fi:1256:8519fbaf22d33984'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(timeline))))
})

async function at(asOf: string) {
  const w = mount(ClaimTimeline, { props: { claimKey: KEY, asOf } })
  await flushPromises()
  return w
}

describe('ClaimTimeline', () => {
  it('fetches the timeline of the claim', async () => {
    await at('')
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toBe('/api/claim/fi/1256/8519fbaf22d33984/timeline')
  })

  it('shows what each edition said at the chosen date', async () => {
    const w2008 = await at('2008-01-01')
    expect(w2008.find('[data-focus-lang="en"]').text()).toContain('the Soviets staged')
    const w2012 = await at('2012-01-01')
    const en = w2012.find('[data-focus-lang="en"]').text()
    expect(en).not.toContain('staged')
    expect(en).toContain('was reported')
  })

  it('says not found in for an edition without a sentence at that date', async () => {
    const w = await at('2008-01-01')
    expect(w.find('[data-focus-lang="de"]').text()).toContain('not found in de')
  })

  it('uses no forbidden word', async () => {
    const w = await at('2012-01-01')
    expect(w.text()).not.toMatch(FORBIDDEN)
  })
})

describe('LifeBars', () => {
  it('draws one bar per life, hatches snapshot ends and explains them', () => {
    const lives = timeline.lives as Life[]
    const w = mount(LifeBars, { props: { lives, asOf: '2012-01-01', claimLang: 'fi' } })
    expect(w.findAll('.life-bars__bar')).toHaveLength(lives.length)
    expect(w.findAll('.life-bars__hatch').length).toBeGreaterThan(0)
    expect(w.text()).toContain('known to the year')
    const en = w.find('[data-lang="en"] .life-bars__bar')
    expect(en.attributes('href')).toBe('https://en.wikipedia.org/w/index.php?oldid=33225464')
    expect(en.attributes('title')).toContain('removed 31 Dec 2009')
  })

  it('draws exact lives without hatching', () => {
    const lives = (timeline.lives as Life[]).map((l) => ({ ...l, time_precision: 'exact' as const }))
    const w = mount(LifeBars, { props: { lives, asOf: '', claimLang: 'fi' } })
    expect(w.findAll('.life-bars__hatch')).toHaveLength(0)
    expect(w.text()).not.toContain('known to the year')
  })
})
