// Chip wording for judge verdicts, shared by every view. Neutral words only (PLAN section 0).
export type ChipStatus = 'success' | 'notice' | 'warning' | 'subtle'

export const VERDICT: Record<string, { label: string; status: ChipStatus }> = {
  same: { label: 'same claim', status: 'success' },
  partial: { label: 'partly the same', status: 'notice' },
  contradicts: { label: 'differs', status: 'warning' },
  different: { label: 'other claim', status: 'subtle' },
}
