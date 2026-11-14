// Dates the slider snaps to besides 1 January: exact edit dates seen in the data (time_precision 'exact').
import { computed, reactive } from 'vue'

const seen = reactive(new Set<string>())

export function addExactDates(items: { born?: string | null; died?: string | null; time_precision?: string | null }[]) {
  for (const x of items) {
    if (x.time_precision !== 'exact') continue
    for (const t of [x.born, x.died]) if (t) seen.add(t.slice(0, 10))
  }
}

export const exactDates = computed(() => [...seen].sort())
