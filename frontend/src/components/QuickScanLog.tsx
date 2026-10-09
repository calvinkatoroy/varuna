import { api } from '@/api'
import { when } from '@/lib/format'
import { useApiData } from '@/lib/useApiData'

type Row = { at: string; org: string; user: string; target: string; status: string }

// Team view of client quick scans: who ran what and when. The results belong to the client and are never shown here.
export function QuickScanLog() {
  const { data } = useApiData<Row[]>(() => api.pget('/api/quick-scans'), 'prv:/api/quick-scans')
  if (!data || data.length === 0) return null
  return (
    <details className="mt-4 rounded-bento border border-rule bg-card">
      <summary className="min-h-[44px] cursor-pointer px-5 py-3 text-[13.5px] font-semibold text-ink">
        Client quick scans <span className="font-normal text-ink-muted">({data.length}, log only, results stay with the client)</span>
      </summary>
      <div className="overflow-x-auto border-t border-rule">
        <table className="w-full text-left text-[12.5px]">
          <thead className="text-ink-faint"><tr><th className="px-5 py-2 font-medium">When</th><th className="px-3 py-2 font-medium">Organization</th><th className="px-3 py-2 font-medium">User</th><th className="px-3 py-2 font-medium">Target</th><th className="px-5 py-2 font-medium">Status</th></tr></thead>
          <tbody>
            {data.map((r, i) => (
              <tr key={i} className="border-t border-rule text-ink">
                <td className="whitespace-nowrap px-5 py-2">{when(r.at)}</td><td className="px-3 py-2">{r.org}</td><td className="px-3 py-2">{r.user}</td>
                <td className="mono px-3 py-2">{r.target}</td><td className="px-5 py-2">{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
