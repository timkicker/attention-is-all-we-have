import { describe, expect, it } from 'vitest'
import { noteText } from '../copy'
import { agrees, comparable, analyse, changedWords, rank, type Analysed, changesOf, cleanComment, headingOf, otherStatement, removalOf, type EditRaw, kindOf, numberText, numValue, readable, spansFor, type Cell, type Life, type Row } from './topic'

const cell = (o: Partial<Cell>): Cell => ({
  status: 'matched', h: 'h', page_id: 1, text: 'x', gloss: null, dist: 0.1, verdict: null, marks: [],
  born: '2010-01-01T00:00:00Z', died: null, born_rev: 1, died_rev: null, time_precision: 'exact', oldid_url: null, ...o,
}) as Cell

describe('numbers', () => {
  it('reads every spelling of one number', () => {
    expect(numValue('25 904')).toBe(25904)
    expect(numValue('25.904')).toBe(25904)
    expect(numValue('25,904')).toBe(25904)
    expect(numValue('2,5')).toBe(2.5)
  })
  it('writes the other edition number in English', () => {
    expect(numberText('rund 25.000')).toBe('about 25,000')
    expect(numberText('800–1,100')).toBe('800–1,100')
    expect(numberText('956')).toBe('956')
    expect(numberText('десятої частини')).toBeNull()
  })
})

describe('kindOf', () => {
  it('only a contradicting or partial-with-marks match differs', () => {
    expect(kindOf(cell({ verdict: { label: 'contradicts' } }), true)).toBe('differs')
    expect(kindOf(cell({ verdict: { label: 'partial' } }), true)).toBe('open')
    expect(kindOf(cell({ verdict: { label: 'partial' }, marks: [{ kind: 'term', this: 'a', other: 'b' }] }), true)).toBe('differs')
    expect(kindOf(cell({ verdict: { label: 'partial' }, marks: [{ kind: 'term', this: 'a', other: 'None' }] }), true)).toBe('open')
    expect(kindOf(cell({ status: 'candidate' }), true)).toBe('open')
    expect(kindOf(cell({ status: 'not_found' }), true)).toBe('missing')
    expect(kindOf(cell({ status: 'not_found' }), false)).toBe('absent')
    expect(kindOf(cell({ verdict: { label: 'same' } }), true)).toBe('same')
  })
})

describe('analyse', () => {
  const row: Row = {
    row_id: 'fi:1:a',
    section: 'S',
    cells: {
      fi: cell({ status: 'anchor', h: 'a', text: 'Neuvostoliitto lavasti 26 662', gloss: 'The Soviet Union staged 26,662' }),
      sv: cell({ verdict: { label: 'partial' }, marks: [{ kind: 'number', this: '26 662', other: '22 830' }] }),
      en: cell({ verdict: { label: 'contradicts' }, marks: [{ kind: 'term', this: 'lavasti', other: 'reported', this_en: 'staged' }], born: '2009-03-12T00:00:00Z' }),
      de: cell({ verdict: { label: 'same' } }),
      ru: cell({ status: 'not_found' }),
      et: cell({ status: 'not_found' }),
      uk: cell({ status: 'candidate' }),
    },
  }
  const present = new Set(['fi', 'sv', 'en', 'de', 'ru', 'uk'])
  const a = analyse(row, 'fi', present, { en: '2001-11-29' })!
  it('marks numbers by value and terms by their English word', () => {
    expect(a.say.spans.map((s) => a.say.text.slice(s.start, s.end))).toEqual(['staged', '26,662'])
  })
  it('writes the note in reading order, never naming an edition that has no article', () => {
    expect(noteText(a.note)).toBe('Swedish says 22,830 · English says it differently · English changed it in 2009 · Not in Russian · German same')
  })
  it('drops rows where no edition differs', () => {
    const calm: Row = { ...row, cells: { fi: row.cells.fi, de: row.cells.de } }
    expect(analyse(calm, 'fi', present, {})).toBeNull()
  })
  it('finds nothing to mark when the word is unknown', () => {
    expect(spansFor('abc', [{ kind: 'term', this: 'x', other: 'y', this_en: null }])).toEqual([])
  })
  it('drops the infobox field name', () => {
    expect(readable('losses1: 25,904 fallen', '[infobox]')).toBe('25,904 fallen')
    expect(readable('losses1: 25,904 fallen', 'Body')).toBe('losses1: 25,904 fallen')
  })
})

describe('changes', () => {
  it('reports the changed words and ignores punctuation-only edits', () => {
    expect(changedWords('the Soviets staged the shelling', 'an incident was reported near')).toMatchObject({
      from: 'the Soviets staged the shelling',
      to: 'an incident was reported near',
    })
    expect(changedWords('close to the border', 'near the border')).toEqual({ from: 'close to', to: 'near', size: 2 })
    expect(changedWords('«Майнільський', 'Майнільський')).toBeNull()
  })
  it('cleans section markers from edit comments', () => {
    expect(cleanComment('/* Shelling */ rewrote it')).toBe('rewrote it')
    expect(cleanComment('/* Shelling */')).toBeNull()
  })
  it('keeps close edits of three words or more, picks the top five and shows them newest first', () => {
    const e = (o: Partial<EditRaw>): EditRaw => ({
      lang: 'en', rev: 1, date: '2009-08-21T18:00:56Z', time_precision: 'exact', from_text: '', to_text: '',
      from_gloss: null, to_gloss: null, comment: null, near: 0.3, paired: false, ...o,
    })
    const out = changesOf([
      e({ from_text: 'On 26 November, the Soviets staged the shelling of Mainila.', to_text: 'On 26 November, a border incident near the village of Mainila occurred.', comment: '/* Background */ rewrote it', rev: 309285088 }),
      e({ from_text: '«Майнільський', to_text: 'Майнільський', lang: 'uk' }),
      e({ from_text: 'close to the border', to_text: 'near the border' }),
      e({ from_text: 'The League expelled them', to_text: 'The League of Nations expelled the Soviet Union', near: 0.45 }),
      e({ from_text: 'about 25 000 men were killed', to_text: 'about 26 662 men died', date: '2015-01-01T00:00:00Z', time_precision: 'snapshot' }),
    ])
    expect(out.map((c) => c.from)).toEqual(['25 000 men were killed', 'the Soviets staged the shelling of Mainila.'])
    expect(out.map((c) => c.date)).toEqual(['2015-01-01', '2009-08-21'])
    const older = e({ from_text: 'about 25 000 men', to_text: 'about 26 662 men in all', date: '2001-01-01T00:00:00Z' })
    const newer = e({ from_text: 'the war began in winter', to_text: 'the war started in the cold winter', date: '2020-01-01T00:00:00Z' })
    expect(changesOf([older, newer]).map((c) => c.date)).toEqual(['2020-01-01', '2001-01-01'])
    expect(out[0].approx).toBe(true)
    expect(out[1]).toMatchObject({ date: '2009-08-21', to: 'a border incident near the village of Mainila occurred.', comment: 'rewrote it', approx: false })
  })
  it('makes headings that end at a clause, never with an ellipsis', () => {
    expect(headingOf('On 26 November 1939, the Soviet Union staged the Shelling of Mainila, with which it justified the war.')).toBe(
      'On 26 November 1939, the Soviet Union staged the Shelling of Mainila',
    )
    expect(headingOf('The struggle ended in heavy losses for the Red Army.')).toBe('The struggle ended in heavy losses for the Red Army')
    const long = 'word '.repeat(40).trim()
    expect(headingOf(long).length).toBeLessThan(100)
    expect(headingOf(long)).not.toMatch(/…/)
  })
  it('shows a removed sentence first, linked to the last revision that had it, and its removal', async () => {
    const d = {
      lang: 'ru', page_id: 33700, title: 'x', h: 'r1', text: 'инсценированный советской стороной', gloss: 'staged by the Soviet side',
      born: '2012-12-24T20:44:59Z', died: '2014-07-09T10:22:55Z', died_rev: 64106894, died_comment: '/* Переговоры */ cut',
      days: 562, reason: 'none' as const, time_precision: 'exact', last_rev: 63917953,
      last_url: 'https://ru.wikipedia.org/w/index.php?oldid=63917953',
      alive_in: [{ lang: 'sv', h: 's1', text: 'Den 26 november', verdict: null, oldid_url: 'https://sv.wikipedia.org/w/index.php?oldid=1' }],
    }
    const s = await otherStatement({} as never, {} as never, 'ru', 'r1', { text: d.text, gloss: null, url: null }, d)
    expect(s.title).toBe('staged by the Soviet side')
    expect(s.groups.map((g) => g.langs.join())).toEqual(['ru', 'sv'])
    expect(s.groups[0].originals[0].url).toBe('https://ru.wikipedia.org/w/index.php?oldid=63917953')
    expect(removalOf(d)).toMatchObject({ date: '2014-07-09', lang: 'ru', to: '', comment: 'cut', url: 'https://ru.wikipedia.org/w/index.php?oldid=64106894' })
  })
  it('ranks clean marked sentences before infobox fields and long number lists, unmarked last', () => {
    const r = (id: string, spans: number, infobox: boolean, differs: number): Analysed => ({
      id, lang: 'fi', pageId: 1, h: id, say: { text: 'x'.repeat(40), spans: Array.from({ length: spans }, (_, i) => ({ start: i * 2, end: i * 2 + 1 })) },
      original: '', note: [], differs: Array(differs).fill('sv'), contradicts: 0, newest: '', infobox,
    })
    const out = rank([r('box', 4, true, 6), r('list', 3, false, 6), r('plain', 0, false, 6), r('losses', 1, false, 3), r('mainila', 1, false, 5)])
    expect(out.map((x) => x.id)).toEqual(['mainila', 'losses', 'box', 'list', 'plain'])
  })
  it('treats rounded numbers as agreeing and different-scale numbers as not comparable', () => {
    expect(agrees({ this: '48,745', other: 'about 48,000' })).toBe(true)
    expect(agrees({ this: '264,908', other: '265,000' })).toBe(true)
    expect(agrees({ this: '25,904', other: '22,830' })).toBe(false)
    expect(comparable({ this: '48,745', other: 'up to 422' })).toBe(false)
    expect(comparable({ this: '200,000', other: '722' })).toBe(false)
    expect(comparable({ this: '25,904', other: '22,830' })).toBe(true)
  })
})
