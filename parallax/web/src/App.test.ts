import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import topics from '../../contract/examples/topics.json'
import compare from '../../contract/examples/compare.json'
import atlas from '../../contract/examples/atlas.json'
import App from './App.vue'
import { FORBIDDEN } from '../tests/forbidden'

const FOOTER =
  'Independent hackathon project. Not affiliated with or endorsed by the Wikimedia Foundation. Wikipedia is a trademark of the Wikimedia Foundation. Text from Wikipedia under CC BY-SA 4.0, split into sentences.'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const u = String(url)
      return new Response(JSON.stringify(u.startsWith('/api/compare') ? compare : u.startsWith('/api/atlas') ? atlas : topics))
    }),
  )
  window.history.replaceState(null, '', '/compare')
})

describe('App shell', () => {
  it('renders the wordmark, every tab and the footer', async () => {
    const w = mount(App)
    await flushPromises()
    expect(w.text()).toContain('Parallax')
    expect(w.text()).toContain(FOOTER)
    for (const label of ['Compare', 'Time', 'Dropped', 'Check', 'Sources', 'Ask', 'Atlas', 'Under the hood'])
      expect(w.text()).toContain(label)
  })

  it('has no Wikipedia skin classes and no forbidden words', async () => {
    const w = mount(App)
    await flushPromises()
    const classes = w.findAll('*').flatMap((el) => [...el.element.classList])
    expect(classes.filter((c) => c.includes('vector-') || c.includes('mw-'))).toEqual([])
    expect(w.text()).not.toMatch(FORBIDDEN)
  })

  it('reads the view and date from the URL and writes tab changes back', async () => {
    window.history.replaceState(null, '', '/dropped?as_of=2012-06-01')
    const { parse } = await import('./state')
    expect(parse(window.location)).toEqual({ view: 'dropped', topic: 'winterwar', as_of: '2012-06-01', anchor: 'fi', section: '', claim: '', run: '', q: '' })
  })

  it('opens the atlas from its URL', async () => {
    window.history.replaceState(null, '', '/atlas')
    const { parse, state } = await import('./state')
    Object.assign(state, parse(window.location))
    const w = mount(App)
    await flushPromises()
    expect(w.find('[aria-label="Atlas"]').exists()).toBe(true)
  })
})
