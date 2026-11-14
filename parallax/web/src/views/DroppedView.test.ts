import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import dropped from '../../../contract/examples/dropped.json'
import topics from '../../../contract/examples/topics.json'
import type { Topic } from '../api'
import DroppedView from './DroppedView.vue'
import { FORBIDDEN } from '../../tests/forbidden'

const body = {
  ...dropped,
  rows: dropped.rows.map((r) => ({ ...r, last_rev: 60401111, last_url: 'https://ru.wikipedia.org/w/index.php?oldid=60401111' })),
  scale: { fi_lives: 1234567, fi_dead: 400000, fi_dead_1y: 150000, fi_revisions: 862076 },
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body))))
})

async function view() {
  const w = mount(DroppedView, { props: { topics: topics.topics as Topic[] } })
  await flushPromises()
  return w
}

describe('DroppedView', () => {
  it('asks for the topic list with a one year minimum', async () => {
    await view()
    const u = String(vi.mocked(fetch).mock.calls[0][0])
    expect(u).toContain('/api/dropped?')
    expect(u).toContain('topic=winterwar')
    expect(u).toContain('min_days=365')
  })

  it('shows the dropped ru sentence with the editions that still state it', async () => {
    const w = await view()
    const card = w.find('[data-lang="ru"][data-h="ac5853856a89a0eb"]')
    expect(card.text()).toContain('инсценированный советской стороной')
    expect(card.text()).toContain('Russian stopped saying it on 23 Dec 2017')
    expect(card.text()).toContain('machine translation')
    expect(card.text()).toContain('de: same claim')
    expect(card.text()).toContain('fi: nearest, not judged')
    const last = card.findAll('a').find((a) => a.text() === 'Open the last revision that had it')!
    expect(last.attributes('href')).toBe('https://ru.wikipedia.org/w/index.php?oldid=60401111')
    expect(card.find('[data-alive-lang="de"] a').text()).toBe('Open on de.wikipedia')
  })

  it('shows the Finnish scale line', async () => {
    const w = await view()
    expect(w.find('[data-testid="fi-scale"]').text()).toContain('1,234,567 sentence lives from 862,076 revisions')
  })

  it('uses no forbidden word', async () => {
    const w = await view()
    expect(w.text()).not.toMatch(FORBIDDEN)
  })
})
