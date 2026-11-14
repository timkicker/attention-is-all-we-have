// Words the UI never shows (PLAN section 0, neutral wording). Kept in web/tests/ because check-rules
// scans web/src for these words and would flag the list itself.
export const FORBIDDEN = /\b(biased|propaganda|false|wrong|lie|lies|liar)\b/i
