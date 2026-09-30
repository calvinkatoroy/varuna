import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, CheckCircle2, FileText, LogOut, XCircle } from 'lucide-react'
import { api } from '@/api'
import { useAuth } from '@/auth'
import { ThemeToggle } from './ThemeToggle'
import { ClientNav } from './ClientNav'
import { BrandMark } from './BrandMark'
import { useScrollThreshold } from '@/lib/useScrollThreshold'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu'

// Solid bg-card (no backdrop-filter): stacking many blurred/glassed regions this close
// together (nav pill + these 3 + AgentStatus + New Proposal, all in one row) triggers a real
// Chromium compositor limitation where adjacent backdrop-filter regions bleed into each
// other's rendering - not fixable by tuning, only by not having that many at once.
const ctrl = 'relative grid h-11 w-11 place-items-center rounded-full border border-rule bg-card text-ink shadow-[0_4px_14px_rgba(0,0,0,.16)] transition-colors hover:bg-panel'

// Derived from the actual proposals list (not a couple of hardcoded demo lines), so it reflects
// whatever really happened last: a delivered report, a rejection with its reason, or a proposal
// that cleared into review. No push/real-time layer here (this is the mock) - it's read fresh
// whenever the menu is opened, same as everything else in the prototype.
function Notifications() {
  const [items, setItems] = useState<{ icon: React.ReactNode; text: string; when: string }[]>([])
  useEffect(() => {
    api.get('/api/proposals').then((rows: any[]) => {
      const list: { icon: React.ReactNode; text: string; when: string }[] = []
      const delivered = rows.find((p) => p.status === 'delivered')
      if (delivered) list.push({ icon: <FileText size={15} />, text: `Report delivered for ${delivered.target}`, when: delivered.when })
      const rejected = rows.find((p) => p.status === 'rejected')
      if (rejected) list.push({ icon: <XCircle size={15} className="text-crit" />, text: `Proposal rejected: ${rejected.target}`, when: rejected.when })
      const inReview = rows.find((p) => p.status === 'in_review')
      if (inReview) list.push({ icon: <CheckCircle2 size={15} />, text: `Approved, now in review: ${inReview.target}`, when: inReview.when })
      setItems(list)
    }).catch(() => {})
  }, [])
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Notifications" className={ctrl}>
        <Bell size={19} />
        {items.length > 0 && <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-accent ring-2 ring-card" />}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[280px]">
        <DropdownMenuLabel>Notifications</DropdownMenuLabel>
        {items.length === 0 && <div className="px-3 py-4 text-center text-[12.5px] text-ink-faint">Nothing new.</div>}
        {items.map((n) => (
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
  const { logout } = useAuth()
  const [me, setMe] = useState<{ username: string; role: string } | null>(null)
  useEffect(() => { api.get('/api/me').then(setMe).catch(() => {}) }, [])
  const initials = (me?.username ?? 'AC').slice(0, 2).toUpperCase()
  const signOut = () => { logout(); localStorage.removeItem('varuna-activated'); location.assign('/') }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account" className="grid h-11 w-11 place-items-center overflow-hidden rounded-full text-sm font-bold text-white shadow-[0_4px_14px_rgba(0,0,0,.16)]" style={{ background: 'linear-gradient(160deg,#4FB3E8,#0B5FA5)' }}>
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
// scroll (it doesn't need to survive into the shrunk state); the nav pill and every control use
// a plain frosted-glass material and stay opaque throughout - they're what's left once the hero
// has fully shrunk.
export function ClientTopbar() {
  const brandFade = useScrollThreshold<HTMLAnchorElement>(50, 'is-faded')
  return (
    <div className="relative z-10 flex items-center gap-4">
      <Link ref={brandFade} to="/" className="fade-collapse flex items-center gap-[11px] text-[21px] font-bold tracking-[-0.02em] text-[#F2F5EF]" style={{ ['--collapse' as any]: '40px', ['--collapse-mt' as any]: '0px' }}>
        <BrandMark size={32} />
        Varuna
      </Link>
      <ClientNav />
      <div className="flex gap-2.5">
        <ThemeToggle className={ctrl} />
        <Notifications />
        <Account />
      </div>
    </div>
  )
}
