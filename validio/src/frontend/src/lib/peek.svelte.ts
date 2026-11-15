// What the lists last showed, so a detail can show its title before its own answer (plans/003),
// and the row whose title travels into the next page's heading.
import type { ActivityItem } from "./api/types";

export const peek = new Map<string, ActivityItem>();
export const morph = $state({ id: "" });
