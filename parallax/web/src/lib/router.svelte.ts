// A tiny history-API router. App.svelte matches `router.path` against ROUTES and renders the page.
// Links are plain <a href> built with `paths`; a document click handler (installed by App) turns
// same-origin clicks into pushState. `mock` and `date` ride along in every link built by `paths`.

export type RouteName =
  | 'start'
  | 'ingest'
  | 'differences'
  | 'statement'
  | 'removed'
  | 'check'
  | 'checkRun'
  | 'hood'
  | 'devStates'
  | 'notFound'

const ROUTES: [RouteName, RegExp, string[]][] = [
  ['start', /^\/$/, []],
  ['ingest', /^\/t\/([^/]+)\/loading$/, ['qid']],
  ['differences', /^\/t\/([^/]+)$/, ['qid']],
  ['statement', /^\/t\/([^/]+)\/s\/([^/]+)\/([^/]+)\/([^/]+)$/, ['qid', 'lang', 'pageId', 'h']],
  ['removed', /^\/t\/([^/]+)\/removed$/, ['qid']],
  ['check', /^\/t\/([^/]+)\/check$/, ['qid']],
  ['checkRun', /^\/t\/([^/]+)\/check\/([^/]+)$/, ['qid', 'runId']],
  ['hood', /^\/hood$/, []],
  ['devStates', /^\/dev\/states$/, []],
]

export interface Match {
  name: RouteName
  params: Record<string, string>
}

export function match(path: string): Match {
  const clean = path.length > 1 ? path.replace(/\/+$/, '') : path
  for (const [name, rx, keys] of ROUTES) {
    const m = rx.exec(clean)
    if (m) return { name, params: Object.fromEntries(keys.map((k, i) => [k, decodeURIComponent(m[i + 1])])) }
  }
  return { name: 'notFound', params: {} }
}

function read() {
  const loc = typeof location === 'undefined' ? { pathname: '/', search: '' } : location
  return { path: loc.pathname, query: new URLSearchParams(loc.search) }
}

class Router {
  path = $state('/')
  /** Never mutate; call setQuery() or navigate(). */
  query = $state(new URLSearchParams())
  current = $derived(match(this.path))

  constructor() {
    const r = read()
    this.path = r.path
    this.query = r.query
  }

  /** Re-read location (popstate). */
  sync() {
    const r = read()
    this.path = r.path
    this.query = r.query
  }

  navigate(href: string, opts: { replace?: boolean } = {}) {
    const url = new URL(href, location.href)
    if (opts.replace) history.replaceState(null, '', url)
    else history.pushState(null, '', url)
    if (!opts.replace && url.pathname !== this.path) window.scrollTo(0, 0)
    this.sync()
  }

  /** Change query params on the current path. null removes a key. */
  setQuery(changes: Record<string, string | null>, opts: { replace?: boolean } = {}) {
    const q = new URLSearchParams(this.query)
    for (const [k, v] of Object.entries(changes)) {
      if (v === null || v === '') q.delete(k)
      else q.set(k, v)
    }
    const s = q.toString()
    this.navigate(this.path + (s ? `?${s}` : ''), opts)
  }

  get mock(): boolean {
    return this.query.get('mock') === '1'
  }
}

export const router = new Router()

/** Intercepts clicks on same-origin <a href> so links do not reload the page. Installed once by App. */
export function installLinkHandler(): () => void {
  const onClick = (e: MouseEvent) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    const a = (e.target as Element | null)?.closest?.('a')
    if (!a || !a.href || a.target || a.hasAttribute('download')) return
    const url = new URL(a.href)
    if (url.origin !== location.origin || url.pathname.startsWith('/api/')) return
    e.preventDefault()
    router.navigate(url.pathname + url.search + url.hash)
  }
  const onPop = () => router.sync()
  document.addEventListener('click', onClick)
  window.addEventListener('popstate', onPop)
  return () => {
    document.removeEventListener('click', onClick)
    window.removeEventListener('popstate', onPop)
  }
}

// ---------- Link builders ----------

/** Adds the sticky params (mock always, date on topic routes) to a path. */
function withQuery(path: string, extra: Record<string, string | null | undefined> = {}, keepDate = true): string {
  const q = new URLSearchParams()
  const date = router.query.get('date')
  if (keepDate && date) q.set('date', date)
  for (const [k, v] of Object.entries(extra)) if (v) q.set(k, v)
  if (router.mock) q.set('mock', '1')
  const s = q.toString()
  return path + (s ? `?${s}` : '')
}

const enc = encodeURIComponent

export const paths = {
  start: (q?: string) => withQuery('/', { q }, false),
  ingest: (qid: string) => withQuery(`/t/${enc(qid)}/loading`, {}, false),
  differences: (qid: string, extra: { q?: string } = {}) => withQuery(`/t/${enc(qid)}`, extra),
  /** Same page on another date (null = today). */
  differencesOn: (qid: string, date: string | null) => {
    const q = new URLSearchParams()
    if (date) q.set('date', date)
    if (router.mock) q.set('mock', '1')
    const s = q.toString()
    return `/t/${enc(qid)}` + (s ? `?${s}` : '')
  },
  statement: (qid: string, lang: string, pageId: number | string, h: string) =>
    withQuery(`/t/${enc(qid)}/s/${enc(lang)}/${enc(String(pageId))}/${enc(h)}`),
  removed: (qid: string) => withQuery(`/t/${enc(qid)}/removed`),
  check: (qid: string) => withQuery(`/t/${enc(qid)}/check`),
  checkRun: (qid: string, runId: string) => withQuery(`/t/${enc(qid)}/check/${enc(runId)}`),
  hood: (fromQid?: string | null) => withQuery('/hood', { from: fromQid ?? undefined }, false),
  devStates: () => withQuery('/dev/states', {}, false),
}
