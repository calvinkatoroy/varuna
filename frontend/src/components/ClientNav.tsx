import { Link, useLocation } from 'react-router-dom'

// The client pill nav, routes between the four client pages. Shared by the cockpit hero and
// the sub-page shell so the active state is always correct.
const items: [string, string][] = [
  ['Overview', '/'],
  ['Proposals', '/proposals'],
  ['Findings', '/findings'],
  ['Reports', '/reports'],
]

export function ClientNav() {
  const { pathname } = useLocation()
  return (
    <nav className="mx-auto flex gap-[3px] rounded-pill bg-white/[.08] p-[5px] backdrop-blur-md">
      {items.map(([label, to]) => {
        const on = pathname === to
        return (
          <Link
            key={to}
            to={to}
            viewTransition
            className={`rounded-pill px-[17px] py-[9px] text-sm leading-none transition-colors ${
              on ? 'bg-[#F4F6F1] font-semibold text-[#12140F]' : 'font-medium text-[#F2F5EF]/70 hover:text-[#F2F5EF]'
            }`}
          >
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
