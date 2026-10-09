import { NavLink } from 'react-router-dom'
import { CLIENT_NAV } from '@/lib/navItems'

// The client pill nav. The active item comes from the URL (NavLink: aria-current="page" for free) and changes
// instantly: no transition, no sliding pill. Solid bg-card, no backdrop-filter - see ClientTopbar's ctrl comment.
export function ClientNav() {
  return (
    <nav aria-label="Main" className="mx-auto hidden h-[52px] items-center gap-[3px] lg:h-11 md:flex rounded-pill border border-rule bg-card p-1 shadow-[0_4px_14px_rgba(0,0,0,.16)]">
      {CLIENT_NAV.map(({ label, to, end, warm }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onPointerEnter={warm}
          onFocus={warm}
          onPointerDown={warm}
          className={({ isActive }) =>
            `flex h-full items-center rounded-pill px-[15px] text-sm leading-none lg:px-[17px] ${isActive ? 'font-semibold text-white' : 'font-medium text-ink-muted hover:text-ink'}`
          }
          style={({ isActive }) => (isActive ? { background: 'var(--color-brand-red)' } : undefined)}
        >
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
