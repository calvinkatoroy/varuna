// Module-level stale-while-revalidate store. A screen renders what is cached at once and refetches in the
// background; equal requests in flight are shared. Everything is dropped when the signed-in person changes
// (api.ts setToken), so one person's screens can never show for another. No React in here: plain functions.
type Entry = { data: unknown; at: number }

const store = new Map<string, Entry>()
const inflight = new Map<string, Promise<unknown>>()
const watchers = new Map<string, Set<() => void>>()
let epoch = 0   // bumped by clearCache: answers that were already on the wire are not stored

export const cacheGet = <T>(key: string): T | undefined => store.get(key)?.data as T | undefined
export const cacheKeys = (prefix: string): string[] => [...store.keys()].filter((k) => k.startsWith(prefix))

export const cacheEpoch = (): number => epoch

/** The one way to write the cache. Pass the `cacheEpoch()` read when the request started: if `clearCache()`
 *  ran since (another person signed in), the answer is dropped instead of stored. */
export function cacheSet<T>(key: string, data: T, startedAt?: number): void {
  if (startedAt !== undefined && startedAt !== epoch) return
  store.set(key, { data, at: Date.now() })
  watchers.get(key)?.forEach((fn) => fn())
}

/** Called whenever `key` is written (by anyone). Returns the unsubscribe function. */
export function subscribe(key: string, fn: () => void): () => void {
  let set = watchers.get(key)
  if (!set) watchers.set(key, (set = new Set()))
  set.add(fn)
  return () => { set!.delete(fn) }
}

/** Run `fetcher` once per key at a time; the answer is cached. A second caller joins the request in flight. */
export function fetchShared<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const running = inflight.get(key)
  if (running) return running as Promise<T>
  const started = epoch
  const p: Promise<T> = fetcher()
    .then((d) => { cacheSet(key, d, started); return d })
    .finally(() => { if (inflight.get(key) === p) inflight.delete(key) })
  inflight.set(key, p)
  return p
}

/** Warm `key` (nav hover/focus). Skipped when the entry is younger than `maxAgeMs`; errors are swallowed. */
export function prefetch(key: string, fetcher: () => Promise<unknown>, maxAgeMs = 5000): void {
  const e = store.get(key)
  if (e && Date.now() - e.at < maxAgeMs) return
  fetchShared(key, fetcher).catch(() => {})
}

/** Forget every entry whose key starts with `prefix` (after a mutation that makes them wrong). */
export function invalidate(prefix: string): void {
  for (const k of cacheKeys(prefix)) store.delete(k)
}

export function clearCache(): void {
  epoch++
  store.clear()
  inflight.clear()
}
