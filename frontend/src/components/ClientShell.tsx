import { Link } from 'react-router-dom'
import { Bell, Shield } from 'lucide-react'
import { ThemeToggle } from './ThemeToggle'
import { ClientNav } from './ClientNav'

const BAND =
  'radial-gradient(120% 150% at 88% -25%, rgba(242,106,67,.28), transparent 46%),' +
  'linear-gradient(158deg,#154739 0%,#0d211b 62%,#070908 100%)'

// Compact page frame for the client sub-pages (Proposals / Findings / Reports): same brand +
// nav + top-right controls as the cockpit hero, on a shorter band, then a panel for content.
export function ClientShell({
  title, sub, action, children,
}: { title: string; sub?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-[1380px] p-[clamp(10px,2vw,28px)]">
      <header
        className="relative isolate flex min-h-[176px] flex-col overflow-hidden rounded-bento-lg px-[clamp(18px,2.6vw,34px)] pb-[clamp(20px,2.4vw,28px)] pt-[clamp(16px,2vw,24px)] text-[#F2F5EF]"
        style={{ background: BAND, borderRadius: '32px 32px 26px 26px' }}
      >
        <div className="flex items-center gap-4">
          <Link to="/" viewTransition className="flex items-center gap-[11px] text-[21px] font-bold tracking-[-0.02em]">
            <span className="grid h-8 w-8 place-items-center rounded-[10px]" style={{ background: 'conic-gradient(from 210deg,#F26A43,#f4996d,#F26A43)', boxShadow: 'inset 0 0 0 2px rgba(255,255,255,.16)' }}>
              <Shield size={18} className="fill-white text-white" />
            </span>
            Varuna
          </Link>
          <ClientNav />
          <div className="flex gap-2.5">
            <ThemeToggle />
            <button aria-label="Notifications" className="grid h-11 w-11 place-items-center rounded-full bg-white/10 backdrop-blur-md transition-colors hover:bg-white/[.18]"><Bell size={19} /></button>
            <button aria-label="Account" className="grid h-11 w-11 place-items-center overflow-hidden rounded-full text-sm font-bold text-white" style={{ background: 'linear-gradient(160deg,#f4996d,#F26A43)' }}>AC</button>
          </div>
        </div>
        <div className="mt-auto flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[clamp(24px,3.4vw,38px)] font-bold leading-none tracking-[-0.02em]">{title}</h1>
            {sub && <p className="mt-2 text-[13.5px] text-[#F2F5EF]/72">{sub}</p>}
          </div>
          {action}
        </div>
      </header>
      <main className="mt-3.5 rounded-bento-lg bg-panel p-3.5">{children}</main>
    </div>
  )
}
