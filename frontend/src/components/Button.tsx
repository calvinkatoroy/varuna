import { ButtonHTMLAttributes } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'danger'
  busy?: boolean
  busyLabel?: string
}

const CLASS = { primary: 'btn', ghost: 'btn-ghost', danger: 'btn-danger' } as const

export default function Button({
  variant = 'primary',
  busy = false,
  busyLabel,
  disabled,
  children,
  className,
  ...rest
}: Props) {
  return (
    <button
      className={[CLASS[variant], className].filter(Boolean).join(' ')}
      disabled={disabled || busy}
      aria-busy={busy}
      {...rest}
    >
      {busy ? busyLabel ?? 'Working…' : children}
    </button>
  )
}
