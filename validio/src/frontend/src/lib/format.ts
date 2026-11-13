// Formatting for money, dates and the words the pages share.
import type { FactGrade, OptionVerdict, RequestStatus, SteadyLineResult } from "./api/types";
import type { BadgeVariant } from "@arlen/ui-kit/components/ui/badge";

const euro = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const money = (cents: number | undefined): string =>
  cents === undefined ? "" : `${euro.format(cents / 100)}\u00a0€`;

const HELSINKI = "Europe/Helsinki";

export const day = (iso: string): string =>
  new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: HELSINKI }).format(new Date(iso));

export const time = (iso: string): string =>
  new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: HELSINKI }).format(new Date(iso));

export const dayTime = (iso: string): string =>
  new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: HELSINKI }).format(new Date(iso));

export const STATUS: Record<RequestStatus, { label: string; variant: BadgeVariant }> = {
  working: { label: "Working", variant: "outline" },
  ordered_alone: { label: "Ordered alone", variant: "success" },
  waiting: { label: "Waiting for you", variant: "warn" },
  approved: { label: "Approved", variant: "success" },
  ordered: { label: "Ordered after approval", variant: "success" },
  rejected: { label: "Rejected", variant: "destructive" },
  blocked: { label: "Blocked", variant: "destructive" },
};

export const GRADE: Record<FactGrade, { label: string; variant: BadgeVariant }> = {
  attested: { label: "Attested", variant: "success" },
  attested_until: { label: "Attested until", variant: "success" },
  consistent: { label: "Consistent", variant: "success" },
  contradicted: { label: "Contradicted", variant: "destructive" },
  unchecked: { label: "Unchecked", variant: "warn" },
  unknown: { label: "Unknown", variant: "warn" },
  untrusted: { label: "Untrusted", variant: "outline" },
};

export const VERDICT: Record<OptionVerdict, { label: string; variant: BadgeVariant }> = {
  chosen: { label: "Chosen", variant: "success" },
  ranked: { label: "Ranked", variant: "outline" },
  rejected: { label: "Rejected", variant: "destructive" },
  blocked: { label: "Blocked", variant: "destructive" },
  not_deliverable: { label: "Not deliverable", variant: "warn" },
};

export const LINE_RESULT: Record<SteadyLineResult, { label: string; variant: BadgeVariant }> = {
  pending: { label: "Not renewed yet", variant: "outline" },
  renewed: { label: "Renewed alone", variant: "success" },
  split_renewed: { label: "Split, renewed alone", variant: "success" },
  waiting: { label: "Waiting for you", variant: "warn" },
  flagged: { label: "Drift flag", variant: "warn" },
  accepted: { label: "Accepted", variant: "success" },
};

export const FIELD: Record<string, string> = {
  autoLimitCents: "auto limit",
  hardCapCents: "hard cap",
  diet: "diet",
  approvers: "approvers",
};
