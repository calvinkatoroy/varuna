import { useState } from 'react'
import { Check } from 'lucide-react'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { Button } from '@/components/ui/button'
import { ProposalForm } from '@/components/ProposalForm'
import { api } from '@/api'

// In-app New Proposal for an activated client (subsequent proposals after onboarding).
export function NewProposalDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [sent, setSent] = useState(false)
  const close = (v: boolean) => { onOpenChange(v); if (!v) setTimeout(() => setSent(false), 200) }

  return (
    <Drawer open={open} onOpenChange={close}>
      <DrawerContent className="max-w-[520px]">
        {sent ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 p-10 text-center">
            <span className="grid h-14 w-14 place-items-center rounded-full bg-low-bg text-low"><Check size={28} /></span>
            <div>
              <DrawerTitle className="text-[20px] font-bold tracking-[-0.02em] text-ink">Proposal submitted</DrawerTitle>
              <p className="mx-auto mt-2 max-w-[36ch] text-[13.5px] leading-relaxed text-ink-muted">Your lead pentester will verify authorization and approve it before any scan runs. You will see it under Proposals.</p>
            </div>
            <Button size="lg" onClick={() => close(false)}>Done</Button>
          </div>
        ) : (
          <>
            <div className="border-b border-rule p-6">
              <span className="text-[12px] font-medium text-ink-muted">Standard scan</span>
              <DrawerTitle className="mt-1 text-[20px] font-bold tracking-[-0.02em] text-ink">New proposal</DrawerTitle>
              <p className="mt-1 text-[13px] text-ink-muted">Submitted to your lead pentester for approval before any scan runs.</p>
            </div>
            <div className="flex-1 p-6">
              <ProposalForm
                submitLabel="Submit proposal"
                onSubmit={async (payload) => { await api.post('/api/proposals', payload); setSent(true) }}
              />
            </div>
          </>
        )}
      </DrawerContent>
    </Drawer>
  )
}
