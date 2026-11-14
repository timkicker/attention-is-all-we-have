import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AtlasView from './AtlasView.vue'
import { navigate, state } from '../state'
import { atlas5 } from '../../tests/atlas5'
import { FORBIDDEN } from '../../tests/forbidden'

const urls = () => vi.mocked(fetch).mock.calls.map((c) => String(c[0]))

beforeEach(() => {
  navigate({ view: 'atlas', topic: 'winterwar' }, true)
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(atlas5))))
})

describe('AtlasView', () => {
  it('shows counts per coverage and one row per topic', async () => {
    const w = mount(AtlasView)
    await flushPromises()
    expect(urls()[0]).toBe('/api/atlas?sort=wikidata_id&limit=50&offset=0')
    expect(w.findAll('[data-testid="atlas-coverage"]').map((b) => b.text())).toEqual([
      'Every topic 5', 'fi, sv and en 2', 'fi and sv only 1', 'fi and en only 1', 'fi only 1',
    ])
    expect(w.findAll('[data-testid="atlas-row"]')).toHaveLength(5)
    expect(w.text()).not.toMatch(FORBIDDEN)
  })

  it('sorts and filters on the server', async () => {
    const w = mount(AtlasView)
    await flushPromises()
    await w.find('[data-testid="atlas-sort-fi_sv"]').trigger('click')
    await flushPromises()
    expect(urls().at(-1)).toBe('/api/atlas?sort=fi_sv&limit=50&offset=0')
    await w.findAll('[data-testid="atlas-coverage"]')[1].trigger('click')
    await flushPromises()
    expect(urls().at(-1)).toBe('/api/atlas?coverage=all&sort=fi_sv&limit=50&offset=0')
  })

  it('links a topic with deep data to Compare', async () => {
    const w = mount(AtlasView)
    await flushPromises()
    await w.find('.atlas__deep').trigger('click')
    expect(state.view).toBe('compare')
    expect(state.topic).toBe('winterwar')
  })
})
