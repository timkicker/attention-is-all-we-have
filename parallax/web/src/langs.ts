// Edition names shown in the UI, in the order of PLAN section 0.
export const LANG_NAMES: Record<string, string> = {
  fi: 'Finnish',
  sv: 'Swedish',
  de: 'German',
  en: 'English',
  ru: 'Russian',
  et: 'Estonian',
  uk: 'Ukrainian',
}
const RTL = new Set(['ar', 'he', 'fa', 'ur'])

export const langName = (lang: string) => LANG_NAMES[lang] ?? lang
export const langDir = (lang: string) => (RTL.has(lang) ? 'rtl' : 'ltr')

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
}
