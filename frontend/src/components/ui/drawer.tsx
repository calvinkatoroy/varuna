import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

export const Drawer = Dialog.Root
export const DrawerClose = Dialog.Close
export const DrawerTitle = Dialog.Title

export function DrawerContent({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0" />
      <Dialog.Content
        className={cn(
          'fixed right-0 top-0 z-50 flex h-full w-full max-w-[480px] flex-col overflow-y-auto border-l border-rule bg-card shadow-[0_0_80px_rgba(0,0,0,.5)] duration-300 focus:outline-none',
          'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right',
          className,
        )}
      >
        {children}
        <DrawerClose className="absolute right-4 top-4 grid h-9 w-9 place-items-center rounded-full text-ink-muted transition-colors hover:bg-panel hover:text-ink">
          <X size={18} />
        </DrawerClose>
      </Dialog.Content>
    </Dialog.Portal>
  )
}
