import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import check from '../../../contract/examples/check.json'
import checkRecorded from '../../../contract/examples/check_recorded.json'
import CheckView from './CheckView.vue'
import { navigate, state } from '../state'
import { FORBIDDEN } from '../../tests/forbidden'

function respond(u: string, init?: RequestInit) {
  if (u.startsWith('/api/check/recorded')) return checkRecorded
  if (u.startsWith('/api/stats')) return { stats: { judge_eval: { accuracy: 0.84, kappa: 0.71, n: 120 } }, sql: [] }
  if (u === '/api/check' && init?.method === 'POST') return { ...check, source: 'live', run_id: 'live00000001' }
  return check
}

beforeEach(() => {
  navigate({ view: 'check', run: '', as_of: '' }, true)
  vi.stubGlobal('fetch', vi.fn(async (u: string, init?: RequestInit) => new Response(JSON.stringify(respond(String(u), init)))))
})

describe('CheckView', () => {
  it('replays a recorded answer and names its model and the judge', async () => {
    navigate({ run: 'rec000000001' }, true)
    const w = mount(CheckView)
    await flushPromises()
    expect(String(vi.mocked(fetch).mock.calls.map((c) => c[0]))).toContain('/api/check/rec000000001')
    const note = w.find('[data-testid="check-note"]').text()
    expect(note).toContain('Recorded answer from example-model, 14 Nov 2026')
    expect(note).toContain('judged by fake-judge')
    expect(note).toContain('84 % of 120 gold pairs')
  })

  it('shows one chip per edition with stopped saying and not found in', async () => {
    navigate({ run: 'rec000000001' }, true)
    const w = mount(CheckView)
    await flushPromises()
    const first = w.find('[data-idx="0"]')
    expect(first.find('[data-lang="en"]').text()).toBe('en: stopped saying (2009)')
    expect(first.find('[data-lang="fi"]').text()).toBe('fi: says')
    expect(first.find('[data-lang="et"]').text()).toBe('not found in et')
    expect(first.find('[data-evidence-lang="en"] a').attributes('href')).toBe('https://en.wikipedia.org/w/index.php?oldid=33225464')
    expect(w.text()).not.toMatch(FORBIDDEN)
  })

  it('posts a pasted answer and keeps the run in the URL', async () => {
    const w = mount(CheckView)
    await flushPromises()
    await w.find('textarea').setValue('The Shelling of Mainila was staged.')
    await w.findAll('button').find((b) => b.text() === 'Check this answer')!.trigger('click')
    await flushPromises()
    const post = vi.mocked(fetch).mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'POST')!
    expect(JSON.parse(String((post[1] as RequestInit).body))).toEqual({ text: 'The Shelling of Mainila was staged.' })
    expect(state.run).toBe('live00000001')
    expect(w.find('[data-testid="check-note"]').text()).toContain('Live check')
  })
})
