import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AskView from './AskView.vue'
import { navigate, state } from '../state'
import ask from '../../../contract/examples/ask.json'
import { FORBIDDEN } from '../../tests/forbidden'

beforeEach(() => {
  navigate({ view: 'ask', q: '', as_of: '' }, true)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => new Response(JSON.stringify(String(url).startsWith('/api/health') ? { engine: 'fake' } : ask))),
  )
})

describe('AskView', () => {
  it('asks nothing until a question is given', async () => {
    const w = mount(AskView)
    await flushPromises()
    expect(vi.mocked(fetch).mock.calls.map((c) => String(c[0]))).toEqual(['/api/health'])
    expect(w.text()).toContain('writes nothing of its own')
  })

  it('puts the question in the URL and shows one column of quotes per edition', async () => {
    const w = mount(AskView)
    await w.find('input').setValue('Who fired the shots at Mainila?')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(state.q).toBe('Who fired the shots at Mainila?')
    expect(window.location.search).toContain('q=Who+fired')
    expect(vi.mocked(fetch).mock.calls.map((c) => String(c[0]))).toContain('/api/ask?q=Who+fired+the+shots+at+Mainila%3F')
    expect(w.find('[data-testid="ask-fake"]').exists()).toBe(true)
    expect(w.findAll('[data-testid="ask-edition"]').map((e) => e.attributes('data-lang'))).toEqual(['fi', 'en', 'ru'])
    const fi = w.find('[data-lang="fi"]')
    expect(fi.text()).toContain('machine translation')
    expect(fi.find('a').attributes('href')).toBe('https://fi.wikipedia.org/w/index.php?oldid=24373824')
    expect(fi.find('a').text()).toBe('Open on fi.wikipedia')
    expect(w.find('[data-lang="en"]').text()).not.toContain('machine translation')
    expect(w.text()).not.toMatch(FORBIDDEN)
  })
})
