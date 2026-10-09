import { NavLink } from 'react-router-dom'
import { CLIENT_NAV } from '@/lib/navItems'

// Phone navigation lives under the thumb, not across the top: the same four places as the desktop pill, one
// tap each, the current one lit (instantly - no transition). Hidden from tablet up (the pill nav returns there).
export function ClientDock() {
  return (
    <nav aria-label="Main" className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-card/95 backdrop-blur md:hidden">
      <ul className="mx-auto grid max-w-[560px] grid-cols-4">
        {CLIENT_NAV.map(({ label, to, end, icon: Icon, warm }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              onPointerDown={warm}
              onFocus={warm}
              className={({ isActive }) =>
                `relative flex min-h-[60px] flex-col items-center justify-center gap-1 text-[12px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus ${isActive ? 'font-semibold text-ink' : 'font-medium text-ink-muted active:text-ink'}`
              }
            >
              {({ isActive }) => (
                <>
                  {/* the lit line is the "you are here" mark, echoing the desktop pill's coral */}
                  <span aria-hidden className={`absolute top-0 h-[3px] rounded-b-full ${isActive ? 'w-9 opacity-100' : 'w-0 opacity-0'}`} style={{ background: 'var(--color-brand-red)' }} />
                  <Icon size={21} strokeWidth={isActive ? 2.4 : 1.9} />
                  {label}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
