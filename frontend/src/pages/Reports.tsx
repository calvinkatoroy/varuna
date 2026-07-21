import { useEffect, useState } from 'react'
import { api, download } from '../api'
import Button from '../components/Button'

export default function Reports() {
  const [items, setItems] = useState<any[]>([])
  const [err, setErr] = useState('')
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  useEffect(() => {
    api
      .get('/api/reports')
      .then(setItems)
      .catch((e) => setErr(e.message))
  }, [])

  async function doDownload(file: string) {
    setDownloadingId(file)
    try {
      await download(api.publicBase, `/api/reports/${file}/download`, file)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <div className="max-w-3xl space-y-md">
      <h1 className="font-display text-display text-ink">Reports</h1>
      {err && <div className="text-sm text-crit">{err}</div>}
      {items.length === 0 && <div className="text-ink-faint">No reports yet. Generate one from a completed scan.</div>}
      {items.map((r) => (
        <div key={r.file} className="card flex items-center justify-between gap-sm">
          <div className="min-w-0 text-sm">
            <div className="truncate text-ink">{r.file}</div>
            <div className="text-xs text-ink-faint">
              {r.template} · {r.ts}
            </div>
          </div>
          <Button
            variant="ghost"
            busy={downloadingId === r.file}
            busyLabel="Downloading…"
            onClick={() => doDownload(r.file)}
          >
            Download
          </Button>
        </div>
      ))}
    </div>
  )
}
