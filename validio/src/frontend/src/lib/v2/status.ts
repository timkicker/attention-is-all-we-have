// The four words every v2 page uses for what happened, and their pill tone.
// Same words everywhere: Ordered automatically, Approved by you, Waiting for you, Blocked, Standing.
import type { ActivityFilter, ActivityItem, ActivityStatus } from "$lib/api/types";
import type { Pill } from "$lib/v";

export const STATUS_PILL: Record<ActivityStatus, Pill> = {
  ordered: { label: "Ordered automatically", tone: "ok" },
  waiting: { label: "Waiting for you", tone: "wait" },
  blocked: { label: "Blocked", tone: "bad" },
  standing: { label: "Standing", tone: "neutral" },
};

/** An order the owner approved is ordered too, but not automatically. */
export const APPROVED_PILL: Pill = { label: "Approved by you", tone: "ok" };

export const pillOf = (item: Pick<ActivityItem, "status" | "approvedByYou">): Pill =>
  item.approvedByYou ? APPROVED_PILL : STATUS_PILL[item.status];

/** The Activity filter chips, in order. */
export const FILTERS: { id: ActivityFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "ordered", label: "Ordered" },
  { id: "waiting", label: "Waiting" },
  { id: "blocked", label: "Blocked" },
  { id: "standing", label: "Standing" },
];

export const isFilter = (v: string | null): v is ActivityFilter => FILTERS.some((f) => f.id === v);
