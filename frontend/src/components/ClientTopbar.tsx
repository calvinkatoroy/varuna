import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, CheckCircle2, FileText, KeyRound, LogOut, Moon, UserRound, XCircle } from 'lucide-react'
import type { ClientTask } from '@/api'
import { useAuth } from '@/auth'
import { ThemeToggle } from './ThemeToggle'
import { ClientNav } from './ClientNav'
import { BrandMark } from './BrandMark'
import { ChangePassword } from './ChangePassword'
import { FEEDS } from '@/lib/feeds'
import { useApiData } from '@/lib/useApiData'
import { useScrollThreshold } from '@/lib/useScrollThreshold'
import { toggleTheme } from '@/lib/theme'
import { roleLabel } from '@/lib/roles'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu'

// Solid bg-card (no backdrop-filter): stacking many blurred/glassed regions this close
// together (nav pill + these 3 + AgentStatus + New task, all in one row) triggers a real
// Chromium compositor limitation where adjacent backdrop-filter regions bleed into each
// other's rendering - not fixable by tuning, only by not having that many at once.
const ctrl = 'relative grid h-11 w-11 flex-none place-items-center rounded-full border border-rule bg-card text-ink shadow-[0_4px_14px_rgba(0,0,0,.16)] transition-colors hover:bg-panel'

type Note = { icon: React.ReactNode; text: string; when: string }

// Derived from the real tasks list: a delivered report, a declined task, a scan that got scheduled. The shell
// is mounted once, so it reads the shared cached tasks feed (one request, and it follows every newer answer
// from the Tasks page poll) instead of fetching on every page.
function useNotifications(): Note[] {
  const { data: rows } = useApiData<ClientTask[]>(FEEDS.tasks.load, FEEDS.tasks.key)
  return useMemo(() => {
    const list: Note[] = []
    const delivered = rows?.find((t) => t.status === 'delivered')
    if (delivered) list.push({ icon: <FileText size={15} />, text: `Report delivered for ${delivered.target}`, when: delivered.when })
    const declined = rows?.find((t) => t.status === 'declined')
    if (declined) list.push({ icon: <XCircle size={15} className="text-crit" />, text: `Task declined: ${declined.target}`, when: declined.when })
    const scheduled = rows?.find((t) => t.status === 'scheduled')
    if (scheduled) list.push({ icon: <CheckCircle2 size={15} />, text: `Scan scheduled: ${scheduled.target}`, when: scheduled.when })
    return list
  }, [rows])
}

function Notifications() {
  const items = useNotifications()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Notifications" className={`${ctrl} hidden md:grid`}>
        <Bell size={19} />
        {items.length > 0 && <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-accent ring-2 ring-card" />}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[280px]">
        <DropdownMenuLabel>Notifications</DropdownMenuLabel>
        {items.length === 0 && <div className="px-3 py-4 text-center text-[12.5px] text-ink-faint">Nothing new.</div>}
        {items.map((n) => (
          <DropdownMenuItem key={n.text} className="items-start gap-2.5">
            <span className="mt-0.5 text-accent-ink">{n.icon}</span>
            <span className="flex-1">
              <span className="block text-[13px] leading-snug text-ink">{n.text}</span>
              <span className="text-[11.5px] text-ink-faint">{n.when}</span>
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function Account() {
  const { user: me, logout } = useAuth()
  const [pw, setPw] = useState(false)
  const notes = useNotifications()
  const initials = (me?.username ?? 'AC').slice(0, 2).toUpperCase()
  const signOut = () => { logout(); localStorage.removeItem('varuna-activated'); location.assign('/') }
  return (
    <>
    {pw && <ChangePassword onClose={() => setPw(false)} />}
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account" className="grid h-11 w-11 flex-none place-items-center overflow-hidden rounded-full text-sm font-bold text-white shadow-[0_4px_14px_rgba(0,0,0,.16)]" style={{ background: 'linear-gradient(160deg,#4FB3E8,#0B5FA5)' }}>
        {initials}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <div className="px-3 py-2">
          <div className="text-[14px] font-semibold text-ink">{me?.username ?? ''}</div>
          <div className="text-[12px] text-ink-muted">{roleLabel(me?.role ?? 'client')}</div>
        </div>
        <DropdownMenuSeparator />
        {/* Phone only: the bell and theme buttons fold into this menu so the header stays quiet. */}
        <div className="md:hidden">
          <DropdownMenuLabel>Notifications</DropdownMenuLabel>
          {notes.length === 0 && <div className="px-3 py-2 text-[12.5px] text-ink-muted">Nothing new.</div>}
          {notes.map((n) => (
            <div key={n.text} className="flex items-start gap-2.5 px-3 py-2">
              <span className="mt-0.5 text-accent-ink">{n.icon}</span>
              <span className="flex-1 text-[13px] leading-snug text-ink">{n.text}</span>
            </div>
          ))}
          <DropdownMenuItem onClick={toggleTheme}><Moon size={15} /> Switch light / dark</DropdownMenuItem>
          <DropdownMenuSeparator />
        </div>
        <DropdownMenuItem asChild><Link to="/profile"><UserRound size={15} /> Profile</Link></DropdownMenuItem>
        <DropdownMenuItem onClick={() => setPw(true)}><KeyRound size={15} /> Change password</DropdownMenuItem>
        <DropdownMenuItem onClick={signOut} className="text-crit"><LogOut size={15} /> Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    </>
  )
}

// The client header: brand + centered nav + working controls. Mounted once inside ClientShell. The brand fades
// out fast on scroll (it doesn't need to survive into the shrunk state); the nav pill and every control stay
// opaque throughout - they're what's left once the hero has fully shrunk.
export function ClientTopbar() {
  const brandFade = useScrollThreshold<HTMLAnchorElement>(50, 'is-faded')
  return (
    <div className="relative z-10 flex items-center gap-4">
      <Link ref={brandFade} to="/" className="fade-collapse flex min-h-[44px] min-w-[44px] items-center gap-[11px] text-[21px] font-bold tracking-[-0.02em] text-[#F2F5EF]" style={{ ['--collapse' as any]: '40px', ['--collapse-mt' as any]: '0px' }}>
        <BrandMark size={32} />
        <span className="md:hidden lg:inline">Varuna</span>
      </Link>
      <ClientNav />
      <div className="ml-auto flex gap-2.5 md:ml-0">
        <ThemeToggle className={`${ctrl} hidden md:grid`} />
        <Notifications />
        <Account />
      </div>
    </div>
  )
}
