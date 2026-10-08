import { useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound, LogOut, Moon, ShieldCheck, UserCog, UserRound } from 'lucide-react'
import { useAuth } from '@/auth'
import { ChangePassword } from './ChangePassword'
import { TwoFactor } from './TwoFactor'
import { toggleTheme } from '@/lib/theme'
import { roleLabel } from '@/lib/roles'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator,
} from './ui/dropdown-menu'

// Shared by every private-plane page (Board, Findings Review, SysAdmin console, Profile) so whoever's
// logged in can always see who they are and sign out, not just from whichever page happens to have it wired up.
export function TeamAccount() {
  const { user: me, logout } = useAuth()
  const [pw, setPw] = useState(false)
  const [tf, setTf] = useState(false)
  const initials = (me?.name ?? me?.username ?? 'TM').slice(0, 2).toUpperCase()
  const signOut = () => { logout(); location.assign('/team') }
  return (
    <>
    {pw && <ChangePassword onClose={() => setPw(false)} />}
    {tf && <TwoFactor onClose={() => setTf(false)} />}
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account" className="grid h-11 w-11 place-items-center rounded-full text-sm font-bold text-white" style={{ background: 'linear-gradient(160deg,#3fb98a,#268a63)' }}>{initials}</DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <div className="px-3 py-2"><div className="text-[14px] font-semibold text-ink">{me?.name ?? me?.username ?? 'Team'}</div><div className="text-[12px] text-ink-muted">{roleLabel(me?.role)}</div></div>
        <DropdownMenuSeparator />
        {me?.role === 'sysadmin' && <DropdownMenuItem asChild><Link to="/team/sysadmin"><UserCog size={15} /> Administration</Link></DropdownMenuItem>}
        <DropdownMenuItem asChild><Link to="/profile"><UserRound size={15} /> Profile</Link></DropdownMenuItem>
        <DropdownMenuItem onClick={toggleTheme} className="md:hidden"><Moon size={15} /> Switch light / dark</DropdownMenuItem>
        <DropdownMenuItem onClick={() => setPw(true)}><KeyRound size={15} /> Change password</DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTf(true)}><ShieldCheck size={15} /> Two-factor authentication</DropdownMenuItem>
        <DropdownMenuItem onClick={signOut} className="text-crit"><LogOut size={15} /> Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    </>
  )
}
