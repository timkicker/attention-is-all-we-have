import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import compare from '../../../contract/examples/compare.json'
import topics from '../../../contract/examples/topics.json'
import CompareView from './CompareView.vue'
import type { Topic } from '../api'
import { FORBIDDEN } from '../../tests/forbidden'

const fetchMock = vi.fn(async (_url: string) => new Response(JSON.stringify(compare), { status: 200 }))

beforeEach(() => {
  fetchMock.mockClear()
  vi.stubGlobal('fetch', fetchMock)
  window.history.replaceState(null, '', '/compare')
})

async function render() {
  const w = mount(CompareView, { props: { topics: topics.topics as Topic[] } })
  await flushPromises()
  return w
}

describe('CompareView', () => {
  it('renders the contract example, one column per edition', async () => {
    const w = await render()
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/compare?topic=winterwar&anchor=fi')
    expect(w.findAll('[role=columnheader]').map((h) => h.attributes('lang'))).toEqual(compare.langs)
    expect(w.findAll('[data-row]')).toHaveLength(compare.rows.length)
  })

  it('says "not found in" for a null cell', async () => {
    const w = await render()
    const cell = w.find('[data-row="fi:1256:6fcbf86eca6b8af2"] [data-lang="sv"]')
    expect(cell.attributes('data-status')).toBe('not_found')
    expect(cell.text()).toContain('not found in sv')
  })

  it('labels glosses as machine translation and links every quote to its oldid', async () => {
    const w = await render()
    const cell = w.find('[data-row="fi:1256:8519fbaf22d33984"] [data-lang="de"]')
    expect(cell.text()).toContain('machine translation')
    expect(cell.find('a').attributes('href')).toBe(compare.rows[0].cells.de.oldid_url)
    expect(cell.find('a').text()).toBe('Open on de.wikipedia')
    expect(cell.find('[lang=de]').exists()).toBe(true)
  })

  it('marks differing numbers and terms in place', async () => {
    const w = await render()
    const en = w.find('[data-row="fi:1256:6fcbf86eca6b8af2"] [data-lang="en"]')
    expect(en.find('mark').text()).toBe('25,904')
    expect(en.text()).toContain('number differs')
    expect(en.text()).toContain('differs')
    const de = w.find('[data-row="fi:1256:8519fbaf22d33984"] [data-lang="de"]')
    expect(de.text()).toContain('uses the term')
  })

  it('uses no forbidden word and no Wikipedia skin class', async () => {
    const w = await render()
    expect(w.text()).not.toMatch(FORBIDDEN)
    const classes = w.findAll('*').flatMap((el) => [...el.element.classList])
    expect(classes.filter((c) => c.includes('vector-') || c.includes('mw-'))).toEqual([])
  })

  it('emits open with the cell when a sentence is clicked', async () => {
    const w = await render()
    await w.find('[data-row="fi:1256:8519fbaf22d33984"] [data-lang="en"]').trigger('click')
    const [lang, cell] = w.emitted('open')![0] as [string, { h: string }]
    expect(lang).toBe('en')
    expect(cell.h).toBe(compare.rows[0].cells.en.h)
  })
})
