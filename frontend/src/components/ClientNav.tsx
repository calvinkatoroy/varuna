import { Link, useLocation } from 'react-router-dom'

// The client pill nav, routes between the four client pages. Shared by the cockpit hero and
// the sub-page shell so the active state is always correct. Same material as the bottom
// PrototypeSwitcher pill (border-rule + bg-card/90 + plain backdrop-blur, theme-aware) - no SVG
// liquid glass, so it stays legible and consistent whichever theme or backdrop it floats over.
const items: [string, string][] = [
  ['Overview', '/'],
  ['Proposals', '/proposals'],
  ['Findings', '/findings'],
  ['Reports', '/reports'],
]

export function ClientNav() {
  const { pathname } = useLocation()
  return (
    <nav className="mx-auto flex h-11 items-center gap-[3px] rounded-pill border border-rule bg-card/90 p-1 shadow-[0_12px_40px_rgba(0,0,0,.3)] backdrop-blur">
      {items.map(([label, to]) => {
        const on = pathname === to
        return (
          <Link
            key={to}
            to={to}
            style={on ? { viewTransitionName: 'nav-pill' } : undefined}
            className={`flex h-full items-center rounded-pill px-[17px] text-sm leading-none transition-colors ${
              on ? 'bg-accent font-semibold text-white' : 'font-medium text-ink-muted hover:text-ink'
            }`}
          >
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
