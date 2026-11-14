// View models: one type per screen, exactly what the page renders. data.ts returns these,
// either from the fixture (?mock=1) or from the API through an adapter in lib/adapt/.
// Pages never see raw API shapes; adapters never build markup.

export const LANGS = ['fi', 'sv', 'de', 'en', 'ru', 'et', 'uk'] as const
export type Lang = (typeof LANGS)[number]

/** A half-open range [start, end) of UTF-16 offsets into a text. */
export interface Span {
  start: number
  end: number
}

/** Text with highlighted ranges. Rendered by ui/Marked.svelte as <mark> (differs) or <del> (removed). */
export interface MarkedText {
  text: string
  spans: Span[]
}

/** One piece of a note line. strong = the edition names in bold ("<b>Swedish</b> says 22,830"). */
export interface NotePart {
  text: string
  strong?: boolean
  /** Between two groups: not drawn (the groups are spaced apart), read out as ", ". */
  sep?: boolean
}
/** A note line under a statement, in reading order, groups split by sep parts. */
export type Note = NotePart[]

/** Counts shown after the tab names. null = not known yet (the tab shows no number). */
export interface TabCounts {
  differences: number | null
  removed: number | null
}

/** The topic as the UI knows it. qid is the Wikidata id in the URL, topicId the API's id. */
export interface TopicRef {
  qid: string
  topicId: string
  title: string
  /** YYYY-MM-DD of the newest stored revision: "latest" means this day, not today. Unknown = undefined or null. */
  latest?: string | null
}

/** Shared by every topic tab. date = YYYY-MM-DD or null for today. */
export interface TopicPage {
  topic: TopicRef
  counts: TabCounts
  date: string | null
}

// ---------- Start (01, 02) ----------

export interface PreparedTopic {
  qid: string
  title: string
  /** "1939 to 1940" or "1918"; built by copy.years() from from/to. */
  from: number | null
  to: number | null
  href: string
}

export interface ExampleLine {
  lang: Lang
  say: MarkedText
}

export interface StartVM {
  prepared: PreparedTopic[]
  example: {
    topic: TopicRef
    /** Data, not copy: "How four editions tell the Mainila shots". */
    title: string
    lines: ExampleLine[]
    href: string
  } | null
}

export type SearchStatus = 'ready' | 'loading' | 'new' | 'no_finnish'

export interface SearchResult {
  qid: string
  title: string
  description: string
  status: SearchStatus
  /** Seconds to load, for status new (and loading when known). */
  etaS: number | null
  /** ready -> topic page, new/loading -> ingest page, no_finnish -> null (not clickable). */
  href: string | null
}

export interface SearchVM {
  q: string
  results: SearchResult[]
}

// ---------- Ingest (03, 04) ----------

export type IngestState = 'queued' | 'running' | 'usable' | 'done' | 'failed'
export type EditionLoadState = 'waiting' | 'running' | 'done' | 'failed'

export interface IngestEdition {
  lang: Lang
  state: EditionLoadState
  pct: number
  error: string | null
  /** ISO datetime of the next retry when Wikipedia asked us to slow down. */
  retryAt: string | null
}

export interface IngestVM {
  qid: string
  title: string
  state: IngestState
  /** 0..100, the bar. */
  progress: number
  etaS: number | null
  editions: IngestEdition[]
  /** Editions done, Finnish included ("Compare the 4 ready editions"). */
  readyCount: number
  /** Topic page link once state is usable or done. */
  openHref: string | null
  /** The "Faster" offer; null once a since-limited job runs or the job is done. */
  faster: { fromYear: number; toYear: number; since: string; etaS: number } | null
}

// ---------- Differences (05, 07) ----------

export interface DiffRow {
  id: string
  /** The Finnish statement in English, differing part marked. */
  say: MarkedText
  note: Note
  href: string
}

export interface DifferencesVM extends TopicPage {
  /** Present when a past date is shown (07). */
  past: { date: string; missing: Lang[] } | null
  q: string
  rows: DiffRow[]
  /** Rows matching q in total (rows.length <= total). */
  total: number
  /** How many more the "Show N more" button loads (0 = no button). */
  more: number
  /** Set when the date is before some edition existed (12, state 4). */
  beforeArticle: { lang: Lang; startsOn: string } | null
}

// ---------- One statement (06) ----------

export interface StatementGroup {
  /** Editions that tell it with this one wording, Finnish first. */
  langs: Lang[]
  say: MarkedText
  /** The original-language text per edition, for "Show original wording". */
  originals: { lang: Lang; text: string; url: string | null }[]
  /** Each edition's own wording with its side of the marks (shown with "Show original wording"). */
  marked: { lang: Lang; say: MarkedText; url: string | null }[]
}

export interface StatementChange {
  date: string
  lang: Lang
  from: string
  to: string
  comment: string | null
  url: string | null
  /** The date is a yearly snapshot: the change happened on or before it ("By ..."). */
  approx: boolean
}

export interface StatementVM extends TopicPage {
  /** h1, e.g. "Who fired the shots at Mainila". */
  title: string
  groups: StatementGroup[]
  /** Editions without this statement ("Not in Estonian"). */
  missing: Lang[]
  /** Newest first. */
  changes: StatementChange[]
  /** Editions not compared yet for this statement ("Not compared yet in ..."). */
  open: Lang[]
  backHref: string
}

// ---------- Removed (08) ----------

export interface RemovedRow {
  id: string
  /** Statement with the removed part as spans (rendered as <del>). */
  say: MarkedText
  note: Note
  href: string
}

export interface RemovedVM extends TopicPage {
  q: string
  /** Edition filter, null = any edition. */
  edition: Lang | null
  /** Editions the filter offers. */
  editions: Lang[]
  rows: RemovedRow[]
  total: number
  more: number
}

// ---------- Check an AI answer (09, 10) ----------

export interface RecordedAnswer {
  runId: string
  /** Data from the API, e.g. "Gemini on Mainila". Never written in copy. */
  label: string
  href: string
}

export interface CheckVM extends TopicPage {
  recorded: RecordedAnswer[]
}

export type CheckVerdict = 'none' | 'disputed' | 'backed'

export interface CheckRow {
  id: string
  verdict: CheckVerdict
  /** The line above the statement in parts set apart by space, e.g. ["Disputed", "Swedish and Russian say otherwise"]. */
  head: readonly string[]
  say: string
  /** Statement page for evidence; null when no edition has it. */
  href: string | null
}

export interface CheckResultVM extends TopicPage {
  runId: string
  /** Recorded answer label (data) or null for a pasted answer. */
  label: string | null
  /** YYYY-MM-DD the answer was recorded, or null. */
  recordedOn: string | null
  answer: string
  /** The first ~120 characters of answer, ending in "…" when cut. */
  excerpt: string
  summary: { total: number; none: number; disputed: number; backed: number }
  /** Every backed statement is backed by most editions; false says "at least one edition". */
  mostBacked: boolean
  rows: CheckRow[]
  againHref: string
}

// ---------- Under the hood (11) ----------

export interface HoodVM {
  /** The topic the reader came from (?from=qid), for "Back to <topic>". */
  from: TopicRef | null
  /** Topic the numbers are about. */
  topicTitle: string
  versions: number | null
  top1: number | null
  top5: number | null
  queryMs: number | null
  /** Statements embedded per second (stat embed_rate.per_s). */
  embedRate: number | null
  /** The hardware and model that rate was measured on (stat embed_rate.gpu). */
  embedGpu: string | null
  /** Share of hand-checked pairs where the model's decision matched a person's (stat judge_eval.accuracy). */
  judgeAccuracy: number | null
  /** How many hand-checked pairs (stat judge_eval.n). */
  judgeN: number | null
  /** The SQL shown under "The query". */
  sql: string
}

// ---------- Results ----------

/** What went wrong, as a value. status 0 = network. */
export interface Failure {
  status: number
  code: string
  message: string
  /** Seconds to wait (429 rate_limited). */
  retryAfterS?: number
}

export type Result<T> = { ok: true; data: T } | { ok: false; error: Failure }
