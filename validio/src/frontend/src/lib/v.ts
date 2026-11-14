// The pill shape every tag in the app shares (VPill, VStatusRow, the v2 StatusPill).
export type PillTone = "ok" | "wait" | "bad" | "neutral";
export interface Pill {
  label: string;
  tone: PillTone;
}
