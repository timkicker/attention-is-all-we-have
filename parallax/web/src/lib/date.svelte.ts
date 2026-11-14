// The date the topic pages show: the ?date=YYYY-MM-DD query param. Absent = today = latest.
// It applies to every tab and is kept across tab switches, because every link built by
// router `paths` carries it. Pages read `dateState.value`; AsOf writes it with `set()`.

import { FIXTURE_TODAY } from './fixture'
import { isIsoDate, isoToday } from './format'
import { router } from './router.svelte'

class DateState {
  /** YYYY-MM-DD, or null for today. An invalid or future param counts as today. */
  value = $derived.by(() => {
    const d = router.query.get('date')
    if (!d || !isIsoDate(d) || d >= this.today) return null
    return d
  })

  /** Today as YYYY-MM-DD (the fixture's today under ?mock=1, so screenshots never drift). */
  get today(): string {
    return router.mock ? FIXTURE_TODAY : isoToday()
  }

  /** The date to send to the API: the chosen one, or today. */
  get effective(): string {
    return this.value ?? this.today
  }

  /** Show another date (null = back to today). Clears the paging offset. */
  set(date: string | null) {
    router.setQuery({ date: date && date < this.today ? date : null, offset: null })
  }
}

export const dateState = new DateState()
