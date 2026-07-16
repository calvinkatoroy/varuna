import { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth'

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
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col border-r border-border bg-card p-4">
        <div className="mb-6 text-lg font-bold text-white">Varuna</div>
        <nav className="space-y-1">
          {links.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${
                  isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-bg'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto pt-6">
          <div className="mb-2 text-xs text-gray-500">
            {user!.username} · {user!.role}
          </div>
          <button onClick={logout} className="btn-ghost w-full">
            Log out
          </button>
        </div>
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  )
}
