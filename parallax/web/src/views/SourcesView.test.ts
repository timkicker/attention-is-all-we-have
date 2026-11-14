import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SourcesView from './SourcesView.vue'
import { navigate } from '../state'
import { sources7 } from '../../tests/sources7'
import { FORBIDDEN } from '../../tests/forbidden'

beforeEach(() => {
  navigate({ view: 'sources', as_of: '' }, true)
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(sources7))))
})

describe('SourcesView', () => {
  it('draws one ISBN bar per edition in edition order', async () => {
    const w = mount(SourcesView)
    await flushPromises()
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toBe('/api/sources?topic=winterwar')
    expect(w.findAll('[data-testid="isbn-bar"]')).toHaveLength(7)
    expect(w.findAll('[data-testid="sources-edition"]').map((e) => e.attributes('data-lang'))).toEqual([
      'fi', 'sv', 'de', 'en', 'ru', 'et', 'uk',
    ])
  })

  it('says what an edition cites mostly and links its revision', async () => {
    const w = mount(SourcesView)
    await flushPromises()
    const fi = w.find('[data-lang="fi"]')
    expect(fi.text()).toContain('cites mostly Finland books (78 of 82 ISBNs)')
    expect(fi.find('a').attributes('href')).toBe('https://fi.wikipedia.org/w/index.php?oldid=1000')
    expect(w.find('[data-lang="en"] .sources__domains').text()).toContain('books.google.com 9')
    expect(w.text()).not.toMatch(FORBIDDEN)
    expect(w.text()).not.toMatch(/\b(best|worst|most reliable|rank)/i)
  })
})
