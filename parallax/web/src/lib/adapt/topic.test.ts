import { describe, expect, it } from 'vitest'
import { noteText } from '../copy'
import { analyse, changedWords, changesOf, cleanComment, kindOf, numberText, numValue, readable, spansFor, type Cell, type Life, type Row } from './topic'

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
    expect(changedWords('the Soviets staged the shelling', 'an incident was reported near')).toEqual({
      from: 'the Soviets staged the shelling',
      to: 'an incident was reported near',
    })
    expect(changedWords('close to the border', 'near the border')).toEqual({ from: 'close to', to: 'near' })
    expect(changedWords('«Майнільський', 'Майнільський')).toBeNull()
  })
  it('cleans section markers from edit comments', () => {
    expect(cleanComment('/* Shelling */ rewrote it')).toBe('rewrote it')
    expect(cleanComment('/* Shelling */')).toBeNull()
  })
  it('walks back from a paired sentence through the versions it replaced', () => {
    const life = (o: Partial<Life>): Life => ({
      lang: 'en', page_id: 1, h: 'x', text: '', born: null, died: null, born_rev: 0, died_rev: null,
      died_comment: null, time_precision: 'exact', verdict: null, ...o,
    }) as Life
    const lives = [
      life({ lang: 'fi', h: 'a', text: 'Finnish', born_rev: 1 }),
      life({ h: 'b', text: 'a border incident was reported near the village', born_rev: 10, died_rev: 20, died_comment: 'tidy' }),
      life({ h: 'c', text: 'an incident was reported near the Soviet village', born: '2017-12-29T00:00:00Z', born_rev: 20, verdict: { label: 'partial' } }),
    ]
    const out = changesOf(lives, 'fi')
    expect(out).toHaveLength(1)
    expect(out[0]).toMatchObject({ date: '2017-12-29', lang: 'en', from: 'a border incident was reported near the', to: 'an incident was reported near the Soviet', comment: 'tidy' })
  })
})
