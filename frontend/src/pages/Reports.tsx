import { useEffect, useState } from 'react'
import { api, download } from '../api'

export default function Reports() {
  const [items, setItems] = useState<any[]>([])
  const [err, setErr] = useState('')

  useEffect(() => {
    api
      .get('/api/reports')
      .then(setItems)
      .catch((e) => setErr(e.message))
  }, [])

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold text-white">Reports</h1>
      {err && <div className="text-sm text-crit">{err}</div>}
      {items.length === 0 && <div className="text-gray-400">No reports yet. Generate one from a completed scan.</div>}
      {items.map((r) => (
        <div key={r.file} className="card flex items-center justify-between">
          <div className="text-sm">
            <div className="text-white">{r.file}</div>
            <div className="text-xs text-gray-500">
              {r.template} · {r.ts}
            </div>
          </div>
          <button
            className="btn-ghost"
            onClick={() => download(api.publicBase, `/api/reports/${r.file}/download`, r.file)}
          >
            Download
          </button>
        </div>
      ))}
    </div>
  )
}
