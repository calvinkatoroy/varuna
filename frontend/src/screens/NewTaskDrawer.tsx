import { useState } from 'react'
import { Check } from 'lucide-react'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { Button } from '@/components/ui/button'
import { TaskForm } from '@/components/TaskForm'
import { tasks } from '@/api'

// "New task" for an activated client.
export function NewTaskDrawer({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (v: boolean) => void; onCreated?: () => void }) {
  const [sent, setSent] = useState(false)
  const close = (v: boolean) => { onOpenChange(v); if (!v) setTimeout(() => setSent(false), 200) }

  return (
    <Drawer open={open} onOpenChange={close}>
      <DrawerContent className="max-w-[520px]">
        {sent ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 p-10 text-center">
            <span className="grid h-14 w-14 place-items-center rounded-full bg-low-bg text-low"><Check size={28} /></span>
            <div>
              <DrawerTitle className="text-[20px] font-bold tracking-[-0.02em] text-ink">Task sent</DrawerTitle>
              <p className="mx-auto mt-2 max-w-[36ch] text-[13.5px] leading-relaxed text-ink-muted">A pentester will pick it up and plan the scan inside your time limit. Follow it under Tasks.</p>
            </div>
            <Button size="lg" onClick={() => close(false)}>Done</Button>
          </div>
        ) : (
          <>
            <div className="border-b border-rule p-6">
              <DrawerTitle className="text-[20px] font-bold tracking-[-0.02em] text-ink">New task</DrawerTitle>
              <p className="mt-1 text-[13px] text-ink-muted">Tell us what to test and when the scan may run.</p>
            </div>
            <div className="flex-1 p-6">
              <TaskForm onSubmit={async (t) => { await tasks.create(t); setSent(true); onCreated?.() }} />
            </div>
          </>
        )}
      </DrawerContent>
    </Drawer>
  )
}
