import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { ProposalForm } from '@/components/ProposalForm'
import { api } from '@/api'

// In-app New Proposal for an activated client (subsequent proposals after onboarding).
export function NewProposalDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="max-w-[520px]">
        <div className="border-b border-rule p-6">
          <span className="text-[12px] font-medium text-ink-muted">Standard scan</span>
          <DrawerTitle className="mt-1 text-[20px] font-bold tracking-[-0.02em] text-ink">New proposal</DrawerTitle>
          <p className="mt-1 text-[13px] text-ink-muted">Submitted to your lead pentester for approval before any scan runs.</p>
        </div>
        <div className="flex-1 p-6">
          <ProposalForm
            submitLabel="Submit proposal"
            onSubmit={async (payload) => {
              await api.post('/api/proposals', payload)
              onOpenChange(false)
            }}
          />
        </div>
      </DrawerContent>
    </Drawer>
  )
}
