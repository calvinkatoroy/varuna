import * as DM from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'

// modal={false}: don't lock body scroll (that removes the scrollbar and shifts the page under
// the popover). Menus don't need the scroll lock; they close on outside click regardless.
export function DropdownMenu(props: React.ComponentProps<typeof DM.Root>) {
  return <DM.Root modal={false} {...props} />
}
export const DropdownMenuTrigger = DM.Trigger

export function DropdownMenuContent({ className, ...props }: React.ComponentProps<typeof DM.Content>) {
  return (
    <DM.Portal>
      <DM.Content
        sideOffset={6}
        collisionPadding={12}
        align="start"
        className={cn(
          'z-[60] min-w-[210px] max-w-[calc(100vw-24px)] rounded-bento border border-rule bg-card p-1.5 shadow-[0_16px_50px_rgba(0,0,0,.35)]',
          'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95',
          className,
        )}
        {...props}
      />
    </DM.Portal>
  )
}

export function DropdownMenuItem({ className, ...props }: React.ComponentProps<typeof DM.Item>) {
  return (
    <DM.Item
      className={cn(
        'flex min-h-[44px] cursor-pointer items-center gap-2.5 rounded-input px-3 py-2 text-[13px] md:min-h-0 font-medium text-ink outline-none transition-colors focus:bg-panel data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export function DropdownMenuLabel({ className, ...props }: React.ComponentProps<typeof DM.Label>) {
  return <DM.Label className={cn('px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-faint', className)} {...props} />
}

export function DropdownMenuSeparator(props: React.ComponentProps<typeof DM.Separator>) {
  return <DM.Separator className="my-1 h-px bg-rule" {...props} />
}
