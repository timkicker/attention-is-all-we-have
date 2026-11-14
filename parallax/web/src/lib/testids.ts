// Every data-testid the app sets and the e2e specs select. Pages use these constants,
// never a literal. Ids are kebab-case "<area>-<thing>"; rows repeat the same id (select by index
// or by text inside), never a per-row id.
//
// Which route renders which ids:
//   every page          bar, bar-logo, bar-link (when the bar has a right link), foot, foot-hood
//   /                   start-search, start-results, start-result (rows, data-status=ready|loading|new|no_finnish),
//                       start-example, start-example-open, start-prepared (rows)
//   /t/:qid/loading     ingest-title, ingest-progress, ingest-eta, ingest-edition (7 rows, data-lang, data-state),
//                       ingest-open (compare-ready button), ingest-faster, state-edition-failed
//   /t/:qid             topic-title, tab-differences, tab-removed, tab-check, as-of, as-of-pop, as-of-pick (quick picks),
//                       as-of-input, as-of-apply, find-statement, diff-row (rows), show-more, notice-past,
//                       back-to-today, state-skeleton, state-empty-filter, state-clear-search,
//                       state-before-article
//   /t/:qid/s/:lang/:pageId/:h
//                       statement-back, statement-title, statement-group (rows, data-langs="fi,de,uk"),
//                       statement-missing, show-original, change-row (rows), state-skeleton
//   /t/:qid/removed     topic header ids, as-of*, find-statement, removed-edition (filter button),
//                       removed-edition-pop, removed-row (rows), show-more, state-empty-filter
//   /t/:qid/check       topic header ids, check-input, check-recorded (links), check-submit
//   /t/:qid/check/:runId
//                       topic header ids, check-meta, check-again, check-answer, check-whole,
//                       check-summary, check-row (rows, data-verdict=none|disputed|backed)
//   /hood               hood-section (4 sections, data-section=matched|query|numbers|limits), hood-query,
//                       hood-number (rows, data-key=versions|top1|top5|query_ms)
//   /dev/states         every state-* id once

export const TID = {
  // shell
  bar: 'bar',
  barLogo: 'bar-logo',
  barLink: 'bar-link',
  foot: 'foot',
  footHood: 'foot-hood',

  // start (P1)
  startSearch: 'start-search',
  startResults: 'start-results',
  startResult: 'start-result',
  startExample: 'start-example',
  startExampleOpen: 'start-example-open',
  startPrepared: 'start-prepared',

  // ingest (P1)
  ingestTitle: 'ingest-title',
  ingestProgress: 'ingest-progress',
  ingestEta: 'ingest-eta',
  ingestEdition: 'ingest-edition',
  ingestOpen: 'ingest-open',
  ingestFaster: 'ingest-faster',

  // topic header (shell)
  topicTitle: 'topic-title',
  tabDifferences: 'tab-differences',
  tabRemoved: 'tab-removed',
  tabCheck: 'tab-check',
  asOf: 'as-of',
  asOfPop: 'as-of-pop',
  asOfPick: 'as-of-pick',
  asOfInput: 'as-of-input',
  asOfApply: 'as-of-apply',
  findStatement: 'find-statement',
  showMore: 'show-more',

  // differences (P2)
  diffRow: 'diff-row',
  noticePast: 'notice-past',
  backToToday: 'back-to-today',

  // statement (P2)
  statementBack: 'statement-back',
  statementTitle: 'statement-title',
  statementGroup: 'statement-group',
  statementMissing: 'statement-missing',
  showOriginal: 'show-original',
  changeRow: 'change-row',

  // removed (P3)
  removedEdition: 'removed-edition',
  removedEditionPop: 'removed-edition-pop',
  removedRow: 'removed-row',

  // check (P3)
  checkInput: 'check-input',
  checkRecorded: 'check-recorded',
  checkSubmit: 'check-submit',
  checkMeta: 'check-meta',
  checkAgain: 'check-again',
  checkAnswer: 'check-answer',
  checkWhole: 'check-whole',
  checkSummary: 'check-summary',
  checkRow: 'check-row',

  // hood (P4)
  hoodSection: 'hood-section',
  hoodQuery: 'hood-query',
  hoodNumber: 'hood-number',

  // states (P4)
  stateSkeleton: 'state-skeleton',
  stateEmptyFilter: 'state-empty-filter',
  stateClearSearch: 'state-clear-search',
  stateEditionFailed: 'state-edition-failed',
  stateEditionFailedOpen: 'state-edition-failed-open',
  stateBeforeArticle: 'state-before-article',
  stateBeforeArticleLink: 'state-before-article-link',
  stateError: 'state-error',
} as const

export type TestId = (typeof TID)[keyof typeof TID]
