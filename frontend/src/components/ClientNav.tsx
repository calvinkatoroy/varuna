import { Link, useLocation } from 'react-router-dom'

// The client pill nav, routes between the four client pages. Shared by the cockpit hero and
// the sub-page shell so the active state is always correct. Solid bg-card, no backdrop-filter -
// see ClientTopbar's ctrl comment for why (too many adjacent blur regions bleed into each other).
const items: [string, string][] = [
  ['Overview', '/'],
  ['Proposals', '/proposals'],
  ['Findings', '/findings'],
  ['Reports', '/reports'],
]

export function ClientNav() {
  const { pathname } = useLocation()
  return (
    <nav aria-label="Main" className="mx-auto hidden h-12 items-center gap-[3px] lg:h-11 md:flex rounded-pill border border-rule bg-card p-1 shadow-[0_4px_14px_rgba(0,0,0,.16)]">
      {items.map(([label, to]) => {
        const on = pathname === to
        return (
          <Link
            key={to}
            to={to}
            className={`flex h-full items-center rounded-pill px-[15px] text-sm leading-none lg:px-[17px] transition-colors ${
              on ? 'font-semibold text-white' : 'font-medium text-ink-muted hover:text-ink'
            }`}
            style={on ? { background: 'var(--color-brand-red)', viewTransitionName: 'nav-pill' } : undefined}
          >
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
