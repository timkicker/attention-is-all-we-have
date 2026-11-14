// URL state shared by every view: /<view>?topic=&as_of=. The URL is the source of truth so links reproduce a screen.
import { reactive } from 'vue'

export const VIEWS = [
  { name: 'compare', label: 'Compare' },
  { name: 'time', label: 'Time' },
  { name: 'dropped', label: 'Dropped' },
  { name: 'check', label: 'Check' },
  { name: 'sources', label: 'Sources' },
  { name: 'ask', label: 'Ask' },
  { name: 'atlas', label: 'Atlas' },
  { name: 'hood', label: 'Under the hood' },
] as const
export type ViewName = (typeof VIEWS)[number]['name']

export interface UrlState {
  view: ViewName
  topic: string
  as_of: string // '' means today
  anchor: string
  section: string // '' means every section; set by deep links such as /compare?section=Osapuolten%20tappiot
  claim: string // 'lang:page_id:h' of the claim whose timeline is open, '' for none
  run: string // run_id of the checked answer shown in Check, '' for none
}

const DEFAULT_TOPIC = 'winterwar'
const DEFAULT_ANCHOR = 'fi'

export function parse(loc: { pathname: string; search: string }): UrlState {
  const name = loc.pathname.replace(/^\/+|\/+$/g, '')
  const view = (VIEWS.find((v) => v.name === name)?.name ?? 'compare') as ViewName
  const q = new URLSearchParams(loc.search)
  return {
    view,
    topic: q.get('topic') || DEFAULT_TOPIC,
    as_of: q.get('as_of') || '',
    anchor: q.get('anchor') || DEFAULT_ANCHOR,
    section: q.get('section') || '',
    claim: q.get('claim') || '',
    run: q.get('run') || '',
  }
}

export function format(s: UrlState): string {
  const q = new URLSearchParams()
  if (s.topic && s.topic !== DEFAULT_TOPIC) q.set('topic', s.topic)
  if (s.as_of) q.set('as_of', s.as_of)
  if (s.anchor && s.anchor !== DEFAULT_ANCHOR) q.set('anchor', s.anchor)
  if (s.section) q.set('section', s.section)
  if (s.claim) q.set('claim', s.claim)
  if (s.run) q.set('run', s.run)
  const qs = q.toString()
  return `/${s.view}${qs ? `?${qs}` : ''}`
}

export const state = reactive<UrlState>(parse(window.location))

/** Change the URL state; replace=true for slider moves so history is not flooded. */
export function navigate(patch: Partial<UrlState>, replace = false): void {
  Object.assign(state, patch)
  const target = format(state)
  if (target !== window.location.pathname + window.location.search) {
    window.history[replace ? 'replaceState' : 'pushState'](null, '', target)
  }
}

window.addEventListener('popstate', () => Object.assign(state, parse(window.location)))
