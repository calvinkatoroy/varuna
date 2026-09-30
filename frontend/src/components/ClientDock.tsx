import { Link, useLocation } from 'react-router-dom'
import { FilePlus2, FileText, LayoutDashboard, ShieldAlert } from 'lucide-react'

// Phone navigation lives under the thumb, not across the top: the same four places as the desktop
// pill, one tap each, the current one lit. Hidden from tablet up (the pill nav returns there).
const items = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'Proposals', to: '/proposals', icon: FilePlus2 },
  { label: 'Findings', to: '/findings', icon: ShieldAlert },
  { label: 'Reports', to: '/reports', icon: FileText },
]

export function ClientDock() {
  const { pathname } = useLocation()
  return (
    <nav aria-label="Main" className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-card/95 backdrop-blur md:hidden">
      <ul className="mx-auto grid max-w-[560px] grid-cols-4">
        {items.map(({ label, to, icon: Icon }) => {
          const on = pathname === to
          return (
            <li key={to}>
              <Link
                to={to}
                aria-current={on ? 'page' : undefined}
                className={`relative flex min-h-[60px] flex-col items-center justify-center gap-1 text-[12px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus ${on ? 'font-semibold text-ink' : 'font-medium text-ink-muted active:text-ink'}`}
              >
                {/* the lit line is the "you are here" mark, echoing the desktop pill's coral */}
                <span aria-hidden className={`absolute top-0 h-[3px] rounded-b-full transition-all duration-300 ${on ? 'w-9 opacity-100' : 'w-0 opacity-0'}`} style={{ background: 'var(--color-brand-red)' }} />
                <Icon size={21} strokeWidth={on ? 2.4 : 1.9} />
                {label}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
