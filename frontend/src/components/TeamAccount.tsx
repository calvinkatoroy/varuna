import { useEffect, useState } from 'react'
import { LogOut } from 'lucide-react'
import { api } from '@/api'
import { useAuth } from '@/auth'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator,
} from './ui/dropdown-menu'

const roleLabel: Record<string, string> = {
  lead_pentester: 'Lead pentester', pentester: 'Pentester', reporter: 'Reporter', governance: 'Governance', soc: 'SOC',
}

// Shared by every team-plane page (Board, Findings Review) so whoever's logged in can always
// see who they are and sign out, not just from whichever page happens to have it wired up.
export function TeamAccount() {
  const { logout } = useAuth()
  const [me, setMe] = useState<{ username: string; name?: string; role: string } | null>(null)
  useEffect(() => { api.get('/api/me').then(setMe).catch(() => {}) }, [])
  const initials = (me?.name ?? me?.username ?? 'TM').slice(0, 2).toUpperCase()
  const signOut = () => { logout(); location.assign('/team') }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account" className="grid h-11 w-11 place-items-center rounded-full text-sm font-bold text-white" style={{ background: 'linear-gradient(160deg,#3fb98a,#268a63)' }}>{initials}</DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <div className="px-3 py-2"><div className="text-[14px] font-semibold text-ink">{me?.name ?? me?.username ?? 'Team'}</div><div className="text-[12px] text-ink-muted">{me ? roleLabel[me.role] ?? me.role : ''}</div></div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={signOut} className="text-crit"><LogOut size={15} /> Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
