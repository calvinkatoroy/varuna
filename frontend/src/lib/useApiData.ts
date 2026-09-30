import { useCallback, useEffect, useState } from 'react'

// GET-on-mount with an actual failure path: api.ts already toasts the error, but a toast is
// transient and a page that's stuck on "Loading..." forever with no way to retry is still a
// dead end. Exposes `setData` too, since a few screens apply local optimistic patches on top
// of the fetched rows (mark fixed, change verdict) rather than always refetching.
export function useApiData<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(() => {
    setError(null)
    fetcher().then(setData).catch((e) => setError(e?.message || 'Something went wrong.'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { reload() }, [reload])

  return { data, error, reload, setData }
}
