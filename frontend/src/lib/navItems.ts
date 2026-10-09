import { FilePlus2, FileText, LayoutDashboard, ShieldAlert, type LucideIcon } from 'lucide-react'
import { FEEDS } from './feeds'

type Icon = LucideIcon
export type NavItem = { label: string; to: string; end?: boolean; icon?: Icon; warm: () => void }

// One table for the pill nav, the phone dock and the team nav. `warm` prefetches that screen's data when the
// link is hovered, focused or pressed, so the click lands on cached data.
export const CLIENT_NAV: (NavItem & { icon: Icon })[] = [
  { label: 'Overview', to: '/', end: true, icon: LayoutDashboard, warm: FEEDS.cockpit.warm },
  { label: 'Tasks', to: '/tasks', icon: FilePlus2, warm: FEEDS.tasks.warm },
  { label: 'Findings', to: '/findings', icon: ShieldAlert, warm: FEEDS.clientTargets.warm },
  { label: 'Reports', to: '/reports', icon: FileText, warm: FEEDS.reports.warm },
]

export const TEAM_NAV: NavItem[] = [
  { label: 'Board', to: '/team', end: true, warm: FEEDS.board.warm },
  { label: 'Findings', to: '/team/findings', warm: FEEDS.teamTargets.warm },
]
