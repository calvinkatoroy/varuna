import { useState } from 'react'
import { Zap } from 'lucide-react'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { Button } from '@/components/ui/button'
import { api } from '@/api'
import { looksPrivate } from '@/components/TaskForm'
import { toast } from '@/lib/toast'

const field = 'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'

// A client's own quick scan of an internal system. Results are theirs alone and are not a verified report.
export function QuickScanDrawer({ open, onOpenChange, onStarted }: { open: boolean; onOpenChange: (v: boolean) => void; onStarted?: () => void }) {
  const [target, setTarget] = useState('')
  const [ok, setOk] = useState(false)
  const [busy, setBusy] = useState(false)
  const hint = target.trim() !== '' && !looksPrivate(target)
  const ready = target.trim() !== '' && ok && !hint && !busy

  async function start(e: React.FormEvent) {
    e.preventDefault()
    if (!ready) return
    setBusy(true)
    try {
      await api.post('/api/quick-scans', { target: target.trim(), consent: true })
      toast('Quick scan started. The results appear under Findings when it finishes.')
      setTarget(''); setOk(false); onOpenChange(false); onStarted?.()
    } catch {
      // api.ts already toasted the reason.
    } finally {
      setBusy(false)
    }
  }

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="max-w-[520px]">
        <div className="border-b border-rule p-6">
          <DrawerTitle className="text-[20px] font-bold tracking-[-0.02em] text-ink">Quick scan</DrawerTitle>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
            Check one of your own internal systems right now, without waiting for a pentester. It runs on your computer with your agent
            and uses the safe profile (it looks for problems, it does not attack).
          </p>
        </div>
        <form onSubmit={start} className="flex-1 space-y-4 p-6">
          <div>
            <label htmlFor="quick-target" className="mb-1.5 block text-[12.5px] font-medium text-ink-muted">Internal address</label>
            <input id="quick-target" className={field} value={target} onChange={(e) => setTarget(e.target.value)} placeholder="http://10.0.0.5:8080" required />
            {hint && (
              <p role="alert" className="mt-2 rounded-input bg-med-bg p-3 text-[12.5px] leading-relaxed text-ink">
                Quick scans only work for internal systems. For a website open on the internet, send a task so a pentester can check the ownership first.
              </p>
            )}
          </div>
          <p className="rounded-input border border-rule bg-panel p-3 text-[12.5px] leading-relaxed text-ink-muted">
            These results are <b className="text-ink">not verified</b> by our security team and are not a report. They may include false alarms.
            You can ask for a verified report from any quick scan result.
          </p>
          <label className="flex min-h-[44px] cursor-pointer items-start gap-3 text-[13px] text-ink">
            <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} className="mt-1 h-4 w-4 flex-none accent-[var(--color-accent)]" />
            <span>I confirm this system belongs to my organization and I am allowed to test it.</span>
          </label>
          <Button type="submit" size="lg" className="w-full" disabled={!ready}>Start quick scan <Zap size={16} /></Button>
          <p className="text-[12px] text-ink-muted">Limits: one quick scan at a time, up to 5 a day for your organization. Our team can see that a quick scan was run, never its results.</p>
        </form>
      </DrawerContent>
    </Drawer>
  )
}
