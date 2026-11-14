// What the demo script (PLAN section 0) shows, per seed. demo.spec.ts picks the row for the seed /api/health reports.
// v1 values were read off seed v1. v3 values are the ones the demo script names; check them when seed v3 lands.
export interface DemoFacts {
  editions: number
  mainila: { row: string; section: string; terms: Record<string, string> }
  dead: { row: string; section: string; fi: string; differs: string[] }
  enFlip: { before: string; after: string; beforeText: string; afterText: string; comment: string | null }
  ruDropped: { text: string; date: string; oldid: number }
  fiScale: boolean
}

const MAINILA = {
  row: 'fi:1256:8519fbaf22d33984',
  section: 'Suomen ja Neuvostoliiton neuvottelut aluemuutoksista',
  terms: { de: 'inszenierte', sv: 'kunnat bevisas', en: 'reported' },
}
const DEAD = { row: 'fi:1256:6fcbf86eca6b8af2', section: 'Osapuolten tappiot', fi: '26 662', differs: ['sv', 'en'] }
const RU_CLAUSE = 'инсценированный советской стороной'

export const FACTS: Record<string, DemoFacts> = {
  v1: {
    editions: 6,
    mainila: MAINILA,
    dead: DEAD,
    // v1 has yearly snapshots: the en sentence is gone in the snapshot after 2009
    enFlip: {
      before: '2008-01-01',
      after: '2018-01-01',
      beforeText: 'the Soviets staged the Shelling of Mainila',
      afterText: 'an incident was reported',
      comment: null,
    },
    ruDropped: { text: RU_CLAUSE, date: '23 Dec 2017', oldid: 60401111 },
    fiScale: false,
  },
  v3: {
    editions: 7,
    mainila: MAINILA,
    dead: DEAD,
    enFlip: {
      before: '2009-08-01',
      after: '2009-09-01',
      beforeText: 'the Soviets staged the Shelling of Mainila',
      afterText: 'an incident was reported',
      comment: 'rewrote the mainila incident part',
    },
    ruDropped: { text: RU_CLAUSE, date: '9 Jul 2014', oldid: 63917953 },
    fiScale: true,
  },
}
