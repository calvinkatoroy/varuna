import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { NewProposalDrawer } from './NewProposalDrawer'

const badge: Record<string, string> = {
  in_review: 'bg-accent-soft text-accent-ink', delivered: 'bg-low-bg text-low',
  scanning: 'bg-[rgba(125,151,216,.16)] text-info', pending: 'bg-med-bg text-med',
}
const badgeLabel: Record<string, string> = {
  in_review: 'In review', delivered: 'Delivered', scanning: 'Scanning', pending: 'Pending approval',
}

export default function ClientProposals() {
  const [rows, setRows] = useState<any[]>([])
  const [open, setOpen] = useState(false)
  useEffect(() => { api.get('/api/proposals').then(setRows) }, [])

  return (
    <ClientShell
      title="Proposals"
      sub="Every scan starts here — approved by your lead pentester before it runs."
      action={<Button variant="glass" size="pill" onClick={() => setOpen(true)}><Plus size={16} /> New Proposal</Button>}
    >
      <div className="overflow-hidden rounded-bento border border-rule bg-card">
        <table className="w-full text-left text-[13.5px]">
          <thead className="border-b border-rule text-[12px] font-semibold uppercase tracking-wide text-ink-faint">
            <tr>
              <th className="px-5 py-3.5">Target</th>
              <th className="px-5 py-3.5">Detail</th>
              <th className="px-5 py-3.5">Submitted</th>
              <th className="px-5 py-3.5 text-right">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-rule first:border-t-0 hover:bg-panel/60">
                <td className="px-5 py-4 font-semibold text-ink">{r.target}</td>
                <td className="px-5 py-4 text-ink-muted">{r.detail}</td>
                <td className="px-5 py-4 text-ink-muted">{r.when}</td>
                <td className="px-5 py-4 text-right">
                  <span className={`inline-block whitespace-nowrap rounded-pill px-[11px] py-1.5 text-[11.5px] font-semibold ${badge[r.status]}`}>{badgeLabel[r.status]}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <NewProposalDrawer open={open} onOpenChange={setOpen} />
    </ClientShell>
  )
}
