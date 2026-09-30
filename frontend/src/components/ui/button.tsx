import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold transition-[opacity,background,color] duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-shell disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:opacity-90',
        accent: 'bg-accent text-accent-foreground hover:opacity-90',
        glass: 'bg-white/[.16] text-[#F2F5EF] hover:bg-white/25',
        outline: 'border border-rule bg-card text-ink hover:bg-panel',
        ghost: 'text-ink-muted hover:text-ink hover:bg-panel',
      },
      size: {
        default: 'h-11 px-5 text-sm rounded-input',
        sm: 'h-9 px-3.5 text-[13px] rounded-input',
        pill: 'h-11 px-5 text-sm rounded-pill',
        lg: 'h-14 px-6 text-[15px] rounded-bento',
        icon: 'h-11 w-11 rounded-full',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return <Comp ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />
  },
)
Button.displayName = 'Button'
