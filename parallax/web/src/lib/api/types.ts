// Raw API response types. Existing routes follow contract/openapi.yaml and contract/examples/*.json;
// search and ingest follow the ui3 brief (agent B builds them). Adapters turn these into view models.

export type Ts = string | null // ISO 8601 UTC, null while alive
export type Url = string | null // https://<lang>.wikipedia.org/...?oldid=

export interface SqlStatement {
  text: string
  ms: number
  rows: number
  index: 'emb' | 'none'
  /** Bound parameters; a list parameter is logged as its length. */
  params?: Record<string, string | number | null | { count: number }>
}

export interface ApiErrorBody {
  error: { code: string; message: string; retry_after_s?: number; [k: string]: unknown }
}

export interface VerdictRef {
  label: 'same' | 'partial' | 'contradicts' | 'different'
  model?: string
  prompt_version?: string
}

export interface MarkRaw {
  kind: 'number' | 'term'
  /** Words in the anchor (Finnish) text. */
  this: string
  /** Words in this edition's original text. */
  other: string
  /** The English word(s) for `this` in the anchor's English gloss, when the API knows them. */
  this_en?: string | null
}

// GET /api/health
export interface HealthRes {
  db: string
  engine: 'fake' | 'real'
  model_id: string
  seed: string
  counts: { claim: number; claim_life_fi: number; verdict: number }
  sql: SqlStatement[]
}

// GET /api/topics
export interface TopicEditionRaw {
  lang: string
  page_id: number
  title: string
  history: 'every' | 'yearly' | 'none'
  revisions: number
  first_ts: Ts
  /** Newest stored revision (data is not refreshed after a load). Older APIs omit it. */
  last_ts?: Ts | null
}
export interface TopicRaw {
  topic_id: string
  label_en: string
  wikidata_id: string
  depth: 'deep' | 'atlas'
  editions: TopicEditionRaw[]
}
export interface TopicsRes {
  topics: TopicRaw[]
  sql: SqlStatement[]
}

// GET /api/compare?topic&as_of&anchor&langs&section&offset&limit
export interface CellRaw {
  status: 'anchor' | 'matched' | 'candidate' | 'not_found'
  h: string | null
  page_id: number | null
  text: string | null
  /** Machine translation into English; null for English cells and for missing ones. */
  gloss: string | null
  dist: number | null
  verdict: VerdictRef | null
  marks: MarkRaw[]
  born: Ts
  died: Ts
  born_rev: number | null
  died_rev: number | null
  time_precision: 'exact' | 'snapshot' | null
  oldid_url: Url
}
export interface CompareRowRaw {
  row_id: string
  section: string
  cells: Record<string, CellRaw>
}
export interface CompareRes {
  topic: string
  as_of: string
  anchor: string
  langs: string[]
  editions: Record<string, { rev_id: number; rev_ts: string }>
  total_rows: number
  rows: CompareRowRaw[]
  sql: SqlStatement[]
}

// GET /api/claim/:lang/:page_id/:h/timeline
export interface LifeRaw {
  lang: string
  page_id: number
  h: string
  text: string
  born: Ts
  died: Ts
  born_rev: number
  died_rev: number | null
  died_comment: string | null
  time_precision: 'exact' | 'snapshot'
  verdict: VerdictRef | null
  /** English gloss of text, when one exists. */
  gloss?: string | null
}
export interface TimelineRes {
  claim: { lang: string; page_id: number; h: string; text: string; section?: string }
  lives: LifeRaw[]
  sql: SqlStatement[]
}

// GET /api/dropped?topic&lang&reason&min_days&offset&limit
export type Reason = 'none' | 'unsourced' | 'error' | 'speculation' | 'other'
export interface DroppedRowRaw {
  lang: string
  page_id: number
  title: string
  h: string
  text: string
  gloss: string | null
  born: Ts
  died: Ts
  died_rev: number
  died_comment: string | null
  days: number
  time_precision?: string
  reason: Reason
  /** Character range of text (or gloss) that was taken out, when known. */
  removed?: { start: number; end: number } | null
  alive_in: { lang: string; h: string; text: string; verdict: VerdictRef | null; oldid_url: Url }[]
}
export interface DroppedRes {
  total: number
  rows: DroppedRowRaw[]
  scale: { fi_lives: number; fi_dead: number; fi_dead_1y: number; fi_revisions: number }
  sql: SqlStatement[]
}

// POST /api/check {text, as_of?, langs?}; GET /api/check/:run_id?as_of
export interface EvidenceRaw {
  lang: string
  page_id: number
  h: string
  text: string
  born: Ts
  died: Ts
  died_rev: number | null
  died_comment: string | null
  dist: number
  verdict: VerdictRef | null
  oldid_url: Url
}
export type CheckLabel = 'says' | 'stopped_saying' | 'contradicts' | 'not_found'
export interface CheckRes {
  run_id: string
  source: 'recorded' | 'live'
  answer_model: string | null
  answer_date: string | null
  engine: 'fake' | 'real'
  claims: { idx: number; text: string; per_lang: Record<string, { label: CheckLabel; evidence: EvidenceRaw[] }> }[]
  /** The checked answer text. */
  text?: string
  /** The question the recorded answer replied to, if any. */
  question?: string | null
  sql: SqlStatement[]
}
export interface CheckReq {
  text: string
  as_of?: string
  langs?: string[]
  /** topic_id: evidence only from this topic. */
  topic?: string
}

// GET /api/check/recorded
export interface CheckRecordedRes {
  runs: { run_id: string; question: string | null; answer_model: string | null; answer_date: string | null }[]
  sql?: SqlStatement[]
}

// GET /api/stats (free-form object of pipeline measurements)
export interface StatsRes {
  stats: Record<string, unknown>
  sql: SqlStatement[]
}

// GET /api/sql/:panel_id
export interface SqlPanelRes {
  panel_id: string
  statements: SqlStatement[]
}

// ---------- New in ui3 (agent B) ----------

// GET /api/search?q=
export type SearchStatusRaw = 'ready' | 'loading' | 'new' | 'no_finnish'
export interface SearchResultRaw {
  qid: string
  title: string
  description: string
  fi_title: string | null
  status: SearchStatusRaw
  eta_s: number | null
}
export interface SearchRes {
  results: SearchResultRaw[]
}

// POST /api/ingest {qid, since?} -> 202 IngestRes (+ job_id); GET /api/ingest/:qid -> IngestRes
export type IngestStateRaw = 'queued' | 'running' | 'usable' | 'done' | 'failed'
export interface IngestEditionRaw {
  lang: string
  state: 'waiting' | 'running' | 'done' | 'failed'
  pct: number
  error: string | null
  retry_at: string | null
}
export interface IngestRes {
  job_id: string
  qid: string
  topic_id: string
  title: string
  state: IngestStateRaw
  eta_s: number | null
  since: string | null
  /** Always 7, order fi sv de en ru et uk. */
  editions: IngestEditionRaw[]
}
export interface IngestReq {
  qid: string
  since?: string
}
