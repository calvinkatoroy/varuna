import { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth'
import Button from './Button'

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const isPro = user!.role === 'pro'

  const links: [string, string][] = [
    ['/new', 'New Scan'],
    ['/scans', 'Active Scans'],
    ...(isPro
      ? ([
          ['/approvals', 'Approval Queue'],
          ['/findings', 'Findings Review'],
          ['/manual', 'Manual Input'],
        ] as [string, string][])
      : []),
    ['/reports', 'Reports'],
    ['/install', 'Install Agent'],
  ]

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside
        className="flex items-center gap-xs overflow-x-auto border-b border-rule bg-paper-2 px-sm py-2xs
                   md:h-screen md:w-56 md:shrink-0 md:flex-col md:items-stretch md:gap-0 md:overflow-visible
                   md:border-b-0 md:border-r md:px-sm md:py-sm"
      >
        <div className="font-display shrink-0 text-lg font-semibold text-ink md:mb-lg">Varuna</div>

        <nav className="flex shrink-0 gap-3xs md:mt-0 md:flex-col">
          {links.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                [
                  'whitespace-nowrap rounded-input border-l-2 px-xs py-2xs text-sm transition-colors duration-short ease-out',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-paper-2',
                  isActive
                    ? 'border-accent bg-paper-3 font-medium text-ink'
                    : 'border-transparent text-ink-muted hover:bg-paper-3 hover:text-ink',
                ].join(' ')
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-xs md:ml-0 md:mt-auto md:flex-col md:items-stretch md:gap-2xs md:pt-lg">
          <div className="hidden text-xs text-ink-faint md:block">
            {user!.username} <span className="mono">· {user!.role}</span>
          </div>
          <Button variant="ghost" onClick={logout} className="w-full">
            Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-sm md:p-lg">{children}</main>
    </div>
  )
}
