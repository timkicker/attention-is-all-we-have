import { describe, expect, it } from 'vitest'
import { FORBIDDEN } from '../../tests/forbidden'
import * as copy from './copy'
import { segments, marked } from './marks'

describe('copy', () => {
  it('names editions, never codes', () => {
    expect(copy.editions(['sv', 'en', 'ru'])).toBe('Swedish, English and Russian')
    expect(copy.edition('xx')).toBe('another edition')
  })
  it('says it differently, singular and plural', () => {
    expect(copy.saysDifferently(['sv', 'en', 'ru'])).toBe('Swedish, English and Russian say it differently')
    expect(copy.saysDifferently(['ru'])).toBe('Russian says it differently')
    expect(copy.saysValue(['sv'], '22,830')).toBe('Swedish says 22,830')
  })
  it('builds note lines with separators and bold names', () => {
    const n = copy.note(copy.saysValueNote(['ru'], '425,640'), [{ text: copy.sameInOthers(5) }])
    expect(copy.noteText(n)).toBe('Russian says 425,640, same in the other five')
    expect(n[0]).toEqual({ text: 'Russian', strong: true })
  })
  it('writes the wireframe sentences', () => {
    expect(copy.notIn(['ru'])).toBe('Not in Russian')
    expect(copy.missingInOthers(4)).toBe('missing in the other four')
    expect(copy.changedItIn('en', 2009)).toBe('English changed it in 2009')
    expect(copy.noteText(copy.removedNote('sv', 'all', '2021-03-03'))).toBe('Swedish removed all of it on 3 Mar 2021')
    expect(copy.noteText(copy.removedNote('en', { words: 'staged' }, '2009-03-12'))).toBe('English removed “staged” on 12 Mar 2009')
    expect(copy.stillIn(['fi', 'de', 'uk'])).toBe('still in Finnish, German and Ukrainian')
    expect(copy.backedBy(6)).toBe('Backed by 6 of 7 editions')
    expect(copy.disputedRemoved(3, 7, 'en', 2009)).toEqual(['Disputed', 'in 3 of 7', 'English removed it in 2009'])
    expect(copy.disputedOtherwise(['sv', 'ru'])).toEqual(['Disputed', 'Swedish and Russian say otherwise'])
    expect(copy.checkSummary({ total: 6, none: 1, disputed: 2, backed: 3 })).toBe(
      'Of 6 statements, 1 is in no edition, 2 are disputed and 3 are backed by most editions',
    )
    expect(copy.checkSummary({ total: 2, none: 0, disputed: 0, backed: 2 }, false)).toBe('Of 2 statements, 2 are backed by at least one edition')
    expect(copy.checkSummary({ total: 0, none: 0, disputed: 0, backed: 0 })).toBe('No statement to check in this answer')
    expect(copy.disputedRemoved(3, 7, ['en', 'ru'], 2014)).toEqual(['Disputed', 'in 3 of 7', 'English and Russian removed it in 2014'])
    expect(copy.notCompared(['ru', 'et'])).toBe('Not compared yet in Russian and Estonian')
    expect(copy.states.othersReady(0)).toBe('None of the others is ready yet')
    expect(copy.states.othersReady(6)).toBe('The other six are ready')
    expect(copy.showingDate('2008-01-01', ['et', 'uk'])).toBe('Showing 1 Jan 2008. Estonian and Ukrainian had no article yet')
    expect(copy.asOf(null)).toBe('As of today')
    expect(copy.asOf('2008-01-01')).toBe('As of 1 Jan 2008')
    expect(copy.asOf(null, '2026-11-03')).toBe('Newest version 3 Nov 2026')
    expect(copy.asOf('2008-01-01', '2026-11-03')).toBe('As of 1 Jan 2008')
    expect(copy.showMore(38)).toBe('Show 38 more')
    expect(copy.start.toLoad(360)).toBe('6 min to load')
    expect(copy.start.faster(2021, 2026, 60)).toBe('Faster: load only 2021 to 2026, about 1 min')
    expect(copy.states.noMatch('volunteers', '2008-01-01')).toBe('No statement matches “volunteers” on 1 Jan 2008')
    expect(copy.states.beforeArticle('et', '2004-03-12', '2006-06-08')).toBe('Estonian had no article on 12 Mar 2004. It starts on 8 Jun 2006')
    expect(copy.years(1939, 1940)).toBe('1939 to 1940')
  })
  it('has no forbidden word, vendor name, exclamation mark or trailing period on a label', () => {
    const strings: string[] = []
    const walk = (v: unknown) => {
      if (typeof v === 'string') strings.push(v)
      else if (v && typeof v === 'object') Object.values(v).forEach(walk)
    }
    walk(copy)
    for (const s of strings) {
      expect(s, s).not.toMatch(FORBIDDEN)
      expect(s, s).not.toMatch(/\b(Gemini|ChatGPT|OpenAI|Google|Anthropic|Claude)\b/)
      expect(s, s).not.toContain('!')
    }
  })
})

describe('marks', () => {
  it('splits text into marked segments', () => {
    expect(segments(marked('the Soviet Union staged the shots', 'staged'))).toEqual([
      { text: 'the Soviet Union ', on: false },
      { text: 'staged', on: true },
      { text: ' the shots', on: false },
    ])
  })
})
