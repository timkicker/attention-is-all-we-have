// THE fixture: the wireframe story in view-model form, served under ?mock=1 by data.ts.
// Winter War (Q134949), today = 14 Nov 2026. Every screen reads from here, so pages agree.
// Where the wireframes and the wireframe BRIEF disagree on story data, the wireframes win
// (Swedish "has never been settled", Finnish Mainila text without the date).
// Recorded-answer labels ("... on Mainila") are data here, never copy.
// Hrefs are built at call time so they carry ?mock=1 and ?date.

import {
  backedBy,
  changedItIn,
  disputedOtherwise,
  disputedRemoved,
  IN_NO_EDITION,
  missingInOthers,
  note,
  notIn,
  removedNote,
  sameIn,
  sameInOthers,
  saysDifferentlyNote,
  saysValueNote,
  stillAgreedThen,
  stillIn,
  excerpt,
} from './copy/shared'
import { all, marked, plain } from './marks'
import type {
  CheckResultVM,
  CheckRow,
  CheckVM,
  DiffRow,
  DifferencesVM,
  HoodVM,
  IngestEdition,
  IngestVM,
  Lang,
  Note,
  RemovedRow,
  RemovedVM,
  Result,
  SearchResult,
  SearchVM,
  StartVM,
  StatementVM,
  TabCounts,
  TopicRef,
} from './model'
import { paths } from './router.svelte'

export const FIXTURE_TODAY = '2026-11-14'

export const WINTER_WAR: TopicRef = { qid: 'Q134949', topicId: 'winterwar', title: 'Winter War' }
export const MANNERHEIM: TopicRef = { qid: 'Q152786', topicId: 'mannerheim', title: 'Carl Gustaf Emil Mannerheim' }

/** Article start per edition for the fixture topic (consistent with 07: Estonian and Ukrainian start after 1 Jan 2008). */
export const STARTS: Record<Lang, string> = {
  fi: '2005-12-31',
  sv: '2005-11-21',
  de: '2005-12-29',
  en: '2005-12-30',
  ru: '2005-12-20',
  et: '2009-12-18',
  uk: '2008-06-02',
}

const t = (s: string): Note => [{ text: s }]
const ok = <T>(data: T): Result<T> => ({ ok: true, data })
const notFound = (what: string): Result<never> => ({
  ok: false,
  error: { status: 404, code: 'topic_not_found', message: `No topic ${what}` },
})

const MAINILA = { lang: 'fi', pageId: 1256, h: '8519fbaf22d33984' }
const LOSSES = { lang: 'fi', pageId: 1256, h: '6fcbf86eca6b8af2' }
const TERRITORY = { lang: 'fi', pageId: 1256, h: '2b7e0c41d9a35f10' }
const LEAGUE = { lang: 'fi', pageId: 1256, h: '9c13a7e5f0b24d68' }
const RED_ARMY = { lang: 'fi', pageId: 1256, h: '5e8d2f9a1c3b7046' }
const stmt = (s: { lang: string; pageId: number; h: string }) => paths.statement(WINTER_WAR.qid, s.lang, s.pageId, s.h)

const FI_MAINILA = 'In the end the Soviet Union staged the Mainila shots to justify the war'
const FI_LOSSES = '26,662 Finns were killed or went missing in the war'
const FI_TERRITORY = 'Finland lost about 11 percent of its territory'
const FI_LEAGUE = 'The League of Nations expelled the Soviet Union on 14 December 1939'
const FI_RED_ARMY = 'The Red Army had about 450,000 men at the start of the war'

export function resolveTopic(qid: string): Result<TopicRef> {
  if (qid === WINTER_WAR.qid) return ok(WINTER_WAR)
  if (qid === MANNERHEIM.qid) return ok(MANNERHEIM)
  return notFound(qid)
}

/** Tab counts: 43 / 302 today, 31 / 118 on any past date (07 shows 1 Jan 2008). */
export function counts(date: string | null): TabCounts {
  return date ? { differences: 31, removed: 118 } : { differences: 43, removed: 302 }
}

// ---------- Start (01, 02) ----------

export function start(): Result<StartVM> {
  return ok({
    prepared: [
      { qid: WINTER_WAR.qid, title: 'Winter War', from: 1939, to: 1940, href: paths.differences(WINTER_WAR.qid) },
      { qid: 'Q193674', title: 'Finnish Civil War', from: 1918, to: null, href: paths.differences('Q193674') },
      { qid: 'Q207645', title: 'Continuation War', from: 1941, to: 1944, href: paths.differences('Q207645') },
      { qid: 'Q623289', title: 'Lapland War', from: 1944, to: 1945, href: paths.differences('Q623289') },
    ],
    example: {
      topic: WINTER_WAR,
      title: 'How four editions tell the Mainila shots',
      lines: [
        { lang: 'fi', say: marked(FI_MAINILA, 'staged') },
        { lang: 'sv', say: marked('Who fired the shots has never been settled', 'has never been settled') },
        { lang: 'en', say: marked('A border incident was reported near Mainila', 'border incident was reported') },
        { lang: 'ru', say: marked('According to the Soviet side, Finnish artillery shelled Mainila', 'Finnish artillery') },
      ],
      href: stmt(MAINILA),
    },
  })
}

const SEARCH: Omit<SearchResult, 'href'>[] = [
  { qid: MANNERHEIM.qid, title: 'Carl Gustaf Emil Mannerheim', description: 'Finnish military leader and president', status: 'new', etaS: 360 },
  { qid: 'Q1129706', title: 'Mannerheim Line', description: 'Defensive line on the Karelian Isthmus', status: 'ready', etaS: null },
  { qid: 'Q3291218', title: 'Mannerheim Museum', description: 'Museum in his former home in Helsinki', status: 'new', etaS: 360 },
  { qid: 'Q1890245', title: 'Mannerheimintie', description: 'Main street of Helsinki', status: 'new', etaS: 360 },
  { qid: WINTER_WAR.qid, title: 'Winter War', description: 'War between the Soviet Union and Finland, 1939 to 1940', status: 'ready', etaS: null },
  { qid: 'Q7959', title: 'Mainila incident', description: 'Shelling of a Soviet border village in 1939', status: 'no_finnish', etaS: null },
]

export function search(q: string): Result<SearchVM> {
  const needle = q.trim().toLowerCase()
  const hits = needle ? SEARCH.filter((r) => r.title.toLowerCase().includes(needle)).slice(0, 6) : []
  return ok({
    q,
    results: hits.map((r) => ({
      ...r,
      href: r.status === 'ready' ? paths.differences(r.qid) : r.status === 'no_finnish' ? null : paths.ingest(r.qid),
    })),
  })
}

// ---------- Ingest (03 = step 1, 04 = step 2) ----------

export function ingest(qid: string, step: number): Result<IngestVM> {
  if (qid !== MANNERHEIM.qid) return notFound(qid)
  const e = (lang: Lang, state: IngestEdition['state'], pct: number): IngestEdition => ({ lang, state, pct, error: null, retryAt: null })
  const ready = step >= 2
  // Step 3: Wikipedia asked us to slow down for Russian; it retries in 2 min, the others are done or running.
  const editions = step >= 3
    ? [e('fi', 'done', 100), e('sv', 'done', 100), e('de', 'done', 100), e('en', 'running', 71), { ...e('ru', 'running', 20), error: 'rate_limited', retryAt: new Date(Date.now() + 120_000).toISOString() }, e('et', 'done', 100), e('uk', 'waiting', 0)]
    : ready
    ? [e('fi', 'done', 100), e('sv', 'done', 100), e('de', 'done', 100), e('en', 'running', 71), e('ru', 'running', 20), e('et', 'done', 100), e('uk', 'waiting', 0)]
    : [e('fi', 'done', 100), e('sv', 'done', 100), e('de', 'running', 91), e('en', 'running', 28), e('ru', 'waiting', 0), e('et', 'waiting', 0), e('uk', 'waiting', 0)]
  return ok({
    qid,
    title: MANNERHEIM.title,
    state: ready ? 'usable' : 'running',
    progress: ready ? 80 : 55,
    etaS: ready ? 120 : 240,
    editions,
    readyCount: editions.filter((x) => x.state === 'done').length,
    openHref: ready ? paths.differences(qid) : null,
    faster: { fromYear: 2021, toYear: 2026, since: '2021-01-01', etaS: 60 },
  })
}

// ---------- Differences (05 today, 07 past) ----------

function diffRowsToday(): DiffRow[] {
  return [
    { id: MAINILA.h, say: marked(FI_MAINILA, 'staged'), note: note(saysDifferentlyNote(['sv', 'en', 'ru']), t(changedItIn('en', 2009))), href: stmt(MAINILA) },
    { id: LOSSES.h, say: marked(FI_LOSSES, '26,662'), note: note(saysValueNote(['sv'], '22,830'), saysValueNote(['de', 'en', 'ru', 'et', 'uk'], '25,904')), href: stmt(LOSSES) },
    { id: TERRITORY.h, say: marked(FI_TERRITORY, '11 percent'), note: note(saysValueNote(['en'], '9 percent'), saysValueNote(['et'], '13 percent'), t(missingInOthers(4))), href: stmt(TERRITORY) },
    { id: LEAGUE.h, say: plain(FI_LEAGUE), note: note(t(notIn(['ru'])), t(sameInOthers(5))), href: stmt(LEAGUE) },
    { id: RED_ARMY.h, say: marked(FI_RED_ARMY, '450,000'), note: note(saysValueNote(['ru'], '425,640'), t(sameInOthers(5))), href: stmt(RED_ARMY) },
  ]
}

function diffRowsPast(): DiffRow[] {
  return [
    { id: MAINILA.h, say: marked(FI_MAINILA, 'staged'), note: note(saysDifferentlyNote(['ru']), t(stillAgreedThen(['en', 'sv']))), href: stmt(MAINILA) },
    { id: LOSSES.h, say: marked(FI_LOSSES, '26,662'), note: note(saysValueNote(['sv'], '22,830'), saysValueNote(['en', 'ru'], '25,904'), t(sameIn(['de']))), href: stmt(LOSSES) },
    { id: LEAGUE.h, say: plain(FI_LEAGUE), note: note(t(notIn(['ru'])), t(sameInOthers(null))), href: stmt(LEAGUE) },
  ]
}

const EARLIEST = Object.values(STARTS).sort()[0]

export function differences(qid: string, date: string | null, o: { q: string; offset: number }): Result<DifferencesVM> {
  if (qid !== WINTER_WAR.qid) return notFound(qid)
  const all7 = date ? diffRowsPast() : diffRowsToday()
  const total = date ? 31 : 43
  const q = o.q.trim().toLowerCase()
  const rows = q ? all7.filter((r) => r.say.text.toLowerCase().includes(q)) : all7
  const missing = date ? (Object.keys(STARTS) as Lang[]).filter((l) => STARTS[l] > date) : []
  const first = date && date < EARLIEST ? null : missing.find((l) => STARTS[l] > (date ?? ''))
  return ok({
    topic: WINTER_WAR,
    counts: counts(date),
    date,
    past: date ? { date, missing } : null,
    q: o.q,
    rows: date && date < EARLIEST ? [] : rows,
    total: q ? rows.length : total,
    more: q ? 0 : total - rows.length,
    beforeArticle: date && date < EARLIEST ? { lang: 'fi', startsOn: STARTS.fi } : first && date && date < '2008-01-01' ? { lang: first, startsOn: STARTS[first] } : null,
  })
}

// ---------- One statement (06) ----------

export function statement(qid: string, date: string | null, _lang: string, _pageId: string, h: string): Result<StatementVM> {
  if (qid !== WINTER_WAR.qid) return notFound(qid)
  const base = { topic: WINTER_WAR, counts: counts(date), date, backHref: paths.differences(WINTER_WAR.qid) }
  if (h === LOSSES.h) {
    return ok({
      ...base,
      title: 'How many Finns died in the war',
      groups: [
        { langs: ['fi'], say: marked(FI_LOSSES, '26,662'), originals: [{ lang: 'fi', text: 'Suomen tappiot talvisodassa olivat 26 662 kaatunutta.', url: 'https://fi.wikipedia.org/w/index.php?oldid=24373824' }], marked: [{ lang: 'fi', say: marked('Suomen tappiot talvisodassa olivat 26 662 kaatunutta.', '26 662'), url: 'https://fi.wikipedia.org/w/index.php?oldid=24373824' }] },
        { langs: ['sv'], say: marked('22,830 Finns were killed or went missing in the war', '22,830'), originals: [{ lang: 'sv', text: 'Omkring 22 830 finländare stupade eller försvann i kriget.', url: null }], marked: [{ lang: 'sv', say: marked('Omkring 22 830 finländare stupade eller försvann i kriget.', '22 830'), url: null }] },
        { langs: ['de', 'en', 'ru', 'et', 'uk'], say: marked('25,904 Finns were killed or went missing in the war', '25,904'), originals: [{ lang: 'en', text: 'Finnish losses were 25,904 dead or missing.', url: null }], marked: [{ lang: 'en', say: marked('Finnish losses were 25,904 dead or missing.', '25,904'), url: null }] },
      ],
      missing: [],
      changes: [],
      open: [],
    })
  }
  if (h !== MAINILA.h) {
    const row = diffRowsToday().find((r) => r.id === h)
    if (!row) return { ok: false, error: { status: 404, code: 'claim_not_found', message: h } }
    return ok({ ...base, title: row.say.text, groups: [{ langs: ['fi'], say: row.say, originals: [], marked: [] }], missing: [], changes: [], open: [] })
  }
  return ok({
    ...base,
    title: 'Who fired the shots at Mainila',
    groups: [
      {
        langs: ['fi', 'de', 'uk'],
        say: marked(FI_MAINILA, 'staged'),
        originals: [
          { lang: 'fi', text: 'Lopulta Neuvostoliitto lavasti Mainilan laukaukset perustellakseen sodan.', url: 'https://fi.wikipedia.org/w/index.php?oldid=24373824' },
          { lang: 'de', text: 'Am Ende inszenierte die Sowjetunion die Schüsse von Mainila, um den Krieg zu rechtfertigen.', url: 'https://de.wikipedia.org/w/index.php?oldid=125967039' },
          { lang: 'uk', text: 'Зрештою Радянський Союз інсценував постріли в Майнілі, щоб виправдати війну.', url: null },
        ],
        marked: [
          { lang: 'fi', say: marked('Lopulta Neuvostoliitto lavasti Mainilan laukaukset perustellakseen sodan.', 'lavasti'), url: 'https://fi.wikipedia.org/w/index.php?oldid=24373824' },
          { lang: 'de', say: marked('Am Ende inszenierte die Sowjetunion die Schüsse von Mainila, um den Krieg zu rechtfertigen.', 'inszenierte'), url: 'https://de.wikipedia.org/w/index.php?oldid=125967039' },
          { lang: 'uk', say: marked('Зрештою Радянський Союз інсценував постріли в Майнілі, щоб виправдати війну.', 'інсценував'), url: null },
        ],
      },
      { langs: ['sv'], say: marked('Who fired the shots has never been settled', 'has never been settled'), originals: [{ lang: 'sv', text: 'Vem som avlossade skotten har aldrig klarlagts.', url: 'https://sv.wikipedia.org/w/index.php?oldid=42191553' }], marked: [{ lang: 'sv', say: marked('Vem som avlossade skotten har aldrig klarlagts.', 'har aldrig klarlagts'), url: 'https://sv.wikipedia.org/w/index.php?oldid=42191553' }] },
      { langs: ['en'], say: marked('A border incident was reported near Mainila', 'border incident was reported'), originals: [{ lang: 'en', text: 'A border incident was reported near Mainila.', url: 'https://en.wikipedia.org/w/index.php?oldid=1384334162' }], marked: [{ lang: 'en', say: marked('A border incident was reported near Mainila.', 'border incident was reported'), url: 'https://en.wikipedia.org/w/index.php?oldid=1384334162' }] },
      { langs: ['ru'], say: marked('According to the Soviet side, Finnish artillery shelled Mainila', 'Finnish artillery'), originals: [{ lang: 'ru', text: 'По данным советской стороны, финская артиллерия обстреляла Майнилу.', url: 'https://ru.wikipedia.org/w/index.php?oldid=155688701' }], marked: [{ lang: 'ru', say: marked('По данным советской стороны, финская артиллерия обстреляла Майнилу.', 'финская артиллерия'), url: 'https://ru.wikipedia.org/w/index.php?oldid=155688701' }] },
    ],
    missing: ['et'],
    changes: [
      { date: '2015-02-04', lang: 'sv', from: 'Soviet troops fired the shots', to: 'has never been settled', comment: null, url: null, approx: false },
      { date: '2009-03-12', lang: 'en', from: 'staged', to: 'a border incident was reported', comment: 'attribute the claim, sources disagree', url: null, approx: false },
    ],
    // Wireframe 06 has no "Not compared yet" line.
    open: [],
  })
}

// ---------- Removed (08) ----------

function removedRows(date: string | null): (RemovedRow & { lang: Lang })[] {
  const r = (id: string, lang: Lang, say: RemovedRow['say'], n: Note) => ({ id, lang, say, note: n, href: stmt({ lang, pageId: 0, h: id }) })
  if (date) {
    return [
      r('a1c4e7f20b3d5968', 'en', marked('The Soviet Union demanded a naval base at Hanko', 'at Hanko'), note(removedNote('en', 'end', '2007-11-05'), t(stillIn(['fi', 'sv', 'de'])))),
      r('b2d5f8031c4e6a79', 'de', all('About 1,000 Swedish volunteers reached the front'), note(removedNote('de', 'all', '2007-02-02'), t(stillIn(['fi', 'sv'])))),
    ]
  }
  return [
    r('c3e6091f2d5b7a80', 'sv', all('About 12,000 foreign volunteers fought on the Finnish side'), note(removedNote('sv', 'all', '2021-03-03'), t(stillIn(['fi', 'de', 'uk'])))),
    r('d4f7102a3e6c8b91', 'de', marked('Stalin expected the Red Army to reach Helsinki within twelve days', 'within twelve days'), note(removedNote('de', 'end', '2017-01-18'), t(stillIn(['fi', 'sv', 'en'])))),
    r('e5081b3f4a7d9ca2', 'ru', all('About 126,875 Soviet soldiers were killed in the war'), note(removedNote('ru', 'all', '2014-07-09'), t(stillIn(['fi', 'sv', 'en'])))),
    r('f6192c4a5b8eadb3', 'en', marked(FI_MAINILA, 'staged'), note(removedNote('en', { words: 'staged' }, '2009-03-12'), t(stillIn(['fi', 'de', 'uk'])))),
  ]
}

export function removed(qid: string, date: string | null, o: { q: string; offset: number; edition: Lang | null }): Result<RemovedVM> {
  if (qid !== WINTER_WAR.qid) return notFound(qid)
  const q = o.q.trim().toLowerCase()
  const filtered = q || o.edition
  const rows = removedRows(date).filter((x) => (!o.edition || x.lang === o.edition) && (!q || x.say.text.toLowerCase().includes(q)))
  const total = filtered ? rows.length : date ? 118 : 302
  return ok({
    topic: WINTER_WAR,
    counts: counts(date),
    date,
    q: o.q,
    edition: o.edition,
    editions: ['fi', 'sv', 'de', 'en', 'ru', 'et', 'uk'],
    rows: rows.map(({ lang: _lang, ...rest }) => rest),
    total,
    more: total - rows.length,
  })
}

// ---------- Check an AI answer (09, 10) ----------

const RUNS = {
  rec000000001: {
    label: 'Gemini on Mainila',
    recordedOn: '2026-11-12',
    answer:
      'Shots were reported at Mainila on 26 November 1939. The Soviet Union staged them to have a reason for war. Mannerheim personally ordered an inquiry at the border. Finnish troops did not fire the shots at Mainila. The Red Army attacked Finland four days later, on 30 November 1939. Finland denied firing and proposed a joint investigation.',
    rows: (): CheckRow[] => [
      { id: '0', verdict: 'none', head: [IN_NO_EDITION], say: 'Mannerheim personally ordered an inquiry at the border', href: null },
      { id: '1', verdict: 'disputed', head: disputedRemoved(3, 7, 'en', 2009), say: 'The Soviet Union staged the shots to have a reason for war', href: stmt(MAINILA) },
      { id: '2', verdict: 'disputed', head: disputedOtherwise(['sv', 'ru']), say: 'Finnish troops did not fire the shots at Mainila', href: stmt(MAINILA) },
      { id: '3', verdict: 'backed', head: [backedBy(7)], say: 'The Red Army attacked Finland four days later, on 30 November 1939', href: stmt(MAINILA) },
      { id: '4', verdict: 'backed', head: [backedBy(6)], say: 'Shots were reported at the border village of Mainila on 26 November 1939', href: stmt(MAINILA) },
      { id: '5', verdict: 'backed', head: [backedBy(5)], say: 'Finland denied firing and proposed a joint investigation', href: stmt(MAINILA) },
    ],
  },
  rec000000002: {
    label: 'ChatGPT on losses',
    recordedOn: '2026-11-12',
    answer:
      'Finland lost 26,662 soldiers in the Winter War. About 126,875 Soviet soldiers were killed. The war ended with the Moscow Peace Treaty on 13 March 1940.',
    rows: (): CheckRow[] => [
      { id: '0', verdict: 'disputed', head: disputedOtherwise(['sv']), say: 'Finland lost 26,662 soldiers in the Winter War', href: stmt(LOSSES) },
      { id: '1', verdict: 'disputed', head: disputedRemoved(3, 7, 'ru', 2014), say: 'About 126,875 Soviet soldiers were killed', href: stmt(LOSSES) },
      { id: '2', verdict: 'backed', head: [backedBy(7)], say: 'The war ended with the Moscow Peace Treaty on 13 March 1940', href: stmt(LEAGUE) },
    ],
  },
} as const

export function check(qid: string, date: string | null): Result<CheckVM> {
  if (qid !== WINTER_WAR.qid) return notFound(qid)
  return ok({
    topic: WINTER_WAR,
    counts: counts(date),
    date,
    recorded: Object.entries(RUNS).map(([runId, r]) => ({ runId, label: r.label, href: paths.checkRun(WINTER_WAR.qid, runId) })),
  })
}

/** A pasted answer always comes back as the Mainila result, unlabeled. */
export function runCheck(text: string): Result<{ runId: string }> {
  if (!text.trim()) return { ok: false, error: { status: 422, code: 'empty_text', message: 'empty' } }
  return ok({ runId: 'live00000001' })
}

export function checkRun(qid: string, date: string | null, runId: string): Result<CheckResultVM> {
  if (qid !== WINTER_WAR.qid) return notFound(qid)
  const known = (RUNS as Record<string, (typeof RUNS)[keyof typeof RUNS]>)[runId]
  const run = known ?? RUNS.rec000000001
  const rows = run.rows()
  return ok({
    topic: WINTER_WAR,
    counts: counts(date),
    date,
    runId,
    label: known ? run.label : null,
    recordedOn: known ? run.recordedOn : null,
    answer: run.answer,
    excerpt: excerpt(run.answer),
    summary: {
      total: rows.length,
      none: rows.filter((r) => r.verdict === 'none').length,
      disputed: rows.filter((r) => r.verdict === 'disputed').length,
      backed: rows.filter((r) => r.verdict === 'backed').length,
    },
    // Wireframe 10: "backed by most editions".
    mostBacked: true,
    rows,
    againHref: paths.check(WINTER_WAR.qid),
  })
}

// ---------- Under the hood (11) ----------

export const HOOD_SQL = `SELECT s.edition, s.text,
  VEC_DISTANCE_COSINE(
    s.embedding, @fi) AS d
FROM statements
  FOR SYSTEM_TIME
  AS OF '2008-01-01' AS s
WHERE s.topic = 'winter-war'
ORDER BY d
LIMIT 5;`

export function hood(fromQid: string | null): Result<HoodVM> {
  const from = fromQid ? resolveTopic(fromQid) : null
  return ok({
    from: from && from.ok ? from.data : null,
    topicTitle: WINTER_WAR.title,
    versions: 15644,
    top1: 0.57,
    top5: 0.89,
    queryMs: 62,
    // Wireframe 11 shows no embedding rate and no model agreement.
    embedRate: null,
    embedGpu: null,
    judgeAccuracy: null,
    judgeN: null,
    sql: HOOD_SQL,
  })
}

// ---------- States (12), exactly the wireframe's examples ----------

export const STATES_EXAMPLE = {
  emptyFilter: { q: 'volunteers', date: '2008-01-01' },
  editionFailed: { lang: 'ru' as Lang, rateLimited: true, othersReady: 6, retryInS: 120 },
  beforeArticle: { lang: 'et' as Lang, date: '2004-03-12', startsOn: '2006-06-08' },
}
