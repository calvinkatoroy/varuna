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

/** The reader's timezone, shown next to every date-time input: "Asia/Jakarta (UTC+07:00)". */
export const TZ_LABEL = (() => {
  const off = -new Date().getTimezoneOffset()
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, '0')
  return `${Intl.DateTimeFormat().resolvedOptions().timeZone} (UTC${off >= 0 ? '+' : '-'}${pad(off / 60)}:${pad(off % 60)})`
})()

/** UTC ISO from the API -> the reader's local date and time. */
export const localTime = (iso?: string | null): string =>
  iso ? new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''

/** <input type="datetime-local"> value (local, no zone) -> UTC ISO with offset, which the API requires. */
export const toUtcIso = (local: string): string => new Date(local).toISOString()

/** UTC ISO -> a datetime-local input value in the reader's timezone. */
export const toLocalInput = (iso: string): string => {
  const d = new Date(iso)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
