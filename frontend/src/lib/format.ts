// Small display helpers so people see what they recognise, not what the database stores.

/** "http://localhost:3000/" -> "localhost:3000": the scheme and trailing slash are noise. */
export const bare = (t: string): string =>
  (t || '').replace(/^[a-z][a-z0-9+.-]*:\/\//i, '').replace(/^www\./, '').replace(/\/$/, '')

const DB_TS = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$/

/**
 * The API stores UTC timestamps like "2026-09-30 08:32:19" (no zone). Show them as the reader's
 * local time: "3 h ago" within a day, "2 d ago" within a week, otherwise "30 Sep 2026". Anything
 * that is not a database timestamp (mock data already says "1d ago") is returned untouched.
 */
export function when(ts: string | undefined | null): string {
  if (!ts || !DB_TS.test(ts)) return ts ?? ''
  const d = new Date(ts.replace(' ', 'T') + 'Z')
  if (isNaN(d.getTime())) return ts
  const mins = Math.round((Date.now() - d.getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  if (mins < 60 * 24) return `${Math.round(mins / 60)} h ago`
  if (mins < 60 * 24 * 7) return `${Math.round(mins / 60 / 24)} d ago`
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
