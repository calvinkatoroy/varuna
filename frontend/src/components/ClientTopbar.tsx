import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, CheckCircle2, FileText, LogOut, Shield } from 'lucide-react'
import { api } from '@/api'
import { ThemeToggle } from './ThemeToggle'
import { ClientNav } from './ClientNav'
import { useLiquidGlassAll } from '@/lib/useLiquidGlass'
import { useScrollFade } from '@/lib/useScrollFade'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu'

const ctrl = 'ctrl-glass relative grid h-11 w-11 place-items-center rounded-full text-[#F2F5EF] transition-colors hover:bg-white/[.10]'

// A couple of read-only demo notifications so the bell is not a dead control.
const notifications = [
  { icon: <FileText size={15} />, text: 'Report delivered for acme.io', when: 'Jun 18' },
  { icon: <CheckCircle2 size={15} />, text: 'Proposal approved: api.acme.io', when: '2h ago' },
]

function Notifications() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Notifications" className={ctrl}>
        <Bell size={19} />
        <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-accent ring-2 ring-[#0d211b]" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[280px]">
        <DropdownMenuLabel>Notifications</DropdownMenuLabel>
        {notifications.map((n) => (
          <DropdownMenuItem key={n.text} className="items-start gap-2.5">
            <span className="mt-0.5 text-accent">{n.icon}</span>
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
  const [me, setMe] = useState<{ username: string; role: string } | null>(null)
  useEffect(() => { api.get('/api/me').then(setMe).catch(() => {}) }, [])
  const initials = (me?.username ?? 'AC').slice(0, 2).toUpperCase()
  const signOut = () => { localStorage.removeItem('varuna-activated'); location.assign('/') }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account" className="ctrl-glass grid h-11 w-11 place-items-center overflow-hidden rounded-full text-sm font-bold text-white" style={{ background: 'linear-gradient(160deg,#f4996d,#F26A43)' }}>
        {initials}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <div className="px-3 py-2">
          <div className="text-[14px] font-semibold text-ink">{me?.username ?? 'acme'}</div>
          <div className="text-[12px] capitalize text-ink-muted">{me?.role ?? 'client'}</div>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={signOut} className="text-crit"><LogOut size={15} /> Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// The client header: brand + centered nav + working controls. Shared by the cockpit hero and
// the sub-page shell so every page has the same, functional top bar. The brand fades out fast on
// scroll (it doesn't need to survive into the shrunk state); the nav pill and every control are
// real liquid glass (not plain blur) and stay opaque throughout - they're what's left once the
// hero has fully shrunk.
export function ClientTopbar() {
  const brandFade = useScrollFade<HTMLAnchorElement>(50)
  useLiquidGlassAll('.ctrl-glass', { scale: -50, blur: 2, mapBlur: 8, saturate: 1.3, chroma: 0, radius: 999 }, [])

  return (
    <div className="relative z-10 flex items-center gap-4">
      <Link ref={brandFade} to="/" className="flex items-center gap-[11px] text-[21px] font-bold tracking-[-0.02em] text-[#F2F5EF]">
        <span className="grid h-8 w-8 place-items-center rounded-[10px]" style={{ background: 'conic-gradient(from 210deg,#F26A43,#f4996d,#F26A43)', boxShadow: 'inset 0 0 0 2px rgba(255,255,255,.16)' }}>
          <Shield size={18} className="fill-white text-white" />
        </span>
        Varuna
      </Link>
      <ClientNav />
      <div className="flex gap-2.5">
        <ThemeToggle className="ctrl-glass" />
        <Notifications />
        <Account />
      </div>
    </div>
  )
}
