// Every visible word of the app. This file is the single import point: pages write
//   import * as copy from '../lib/copy'
//   and read shared words as copy.saysDifferently(...), area words as copy.topic.SUB_DIFFERENCES.
// Shared words (edition names, finding words, tabs, bar, footer, dates, numbers) live in copy/shared.ts
// and are written only there. Area files hold sentences used by one area and import finding words
// from ./shared, never retype them. A visible string typed in a .svelte file is a bug.

export * from './copy/shared'
export * as start from './copy/start'
export * as topic from './copy/topic'
export * as removed from './copy/removed'
export * as check from './copy/check'
export * as hood from './copy/hood'
export * as states from './copy/states'
