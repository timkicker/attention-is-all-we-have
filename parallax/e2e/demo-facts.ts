// What the demo script (PLAN section 0) shows, per seed. demo.spec.ts picks the entry for the seed /api/health reports.
// Only what the audience reads is written here: words of the statements, dates and Wikipedia revision ids.
// The Differences and Removed lists show English translations of the statements; "Show original wording" on a
// statement shows each edition's own words.
export interface DemoFacts {
  // the fi Mainila statement today: words of its English translation, and words each edition uses in its own language
  mainila: { find: string; words: string; originals: Record<string, string> }
  // the fi Finnish dead statement: the number and the editions that give another one
  dead: { find: string; fi: string; differs: string[]; other: string }
  // the fi Mainila statement alive in 2009 (row hash) and the en sentence before and after the 2009 edit
  enFlip: { pageId: number; h: string; before: string; after: string; beforeText: string; afterText: string; year: number }
  // the ru clause removed on 9 Jul 2014, an edition that still has it, and the last ru revision that had it
  ruDropped: { words: RegExp; date: string; alive: string; oldid: number }
  // the Finnish scale line under Removed: how many Finnish versions the sentence lives come from
  fiVersions: number | null
}

export const FACTS: Record<string, DemoFacts> = {
  v4: {
    mainila: {
      find: 'Mainila',
      words: 'staged the Shelling of Mainila',
      originals: { fi: 'lavasti', de: 'inszenierte', sv: 'skotten vid Mainila', en: 'reported' },
    },
    dead: { find: '26,662', fi: '26,662', differs: ['de', 'en', 'uk'], other: '25,904' },
    enFlip: {
      pageId: 1256,
      h: '6777cf5a519b4fe9',
      before: '2009-08-01',
      after: '2010-01-01',
      beforeText: 'the Soviets staged the shelling of Mainila',
      afterText: 'a border incident was reported',
      year: 2009,
    },
    ruDropped: {
      words: /staged by the Soviet side|инсценированный советской стороной/,
      date: '2014-07-09',
      alive: 'de',
      oldid: 63917953,
    },
    fiVersions: 862076,
  },
}
