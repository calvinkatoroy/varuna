import { ClientTopbar } from './ClientTopbar'
import { useScrollThreshold } from '@/lib/useScrollThreshold'

const BAND =
  'radial-gradient(120% 150% at 88% -25%, rgba(242,106,67,.28), transparent 46%),' +
  'linear-gradient(158deg,#154739 0%,#0d211b 62%,#070908 100%)'

// Compact page frame for the client sub-pages (Proposals / Findings / Reports): one merged
// sticky hero (brand/nav/controls + title), matching the cockpit. Shrink/fade on scroll is a
// threshold class toggle (useScrollThreshold), not a continuously-scrubbed value - see that
// file for why (padding/max-height are layout properties; scrubbing them every scroll frame,
// JS-driven or via native scroll-timeline, forces a reflow either way).
export function ClientShell({
  title, sub, action, children,
}: { title: string; sub?: string; action?: React.ReactNode; children: React.ReactNode }) {
  const shrink = useScrollThreshold<HTMLElement>(60, 'is-shrunk')
  const fade = useScrollThreshold<HTMLDivElement>(55, 'is-faded')
  return (
    <div className="mx-auto max-w-[1380px] p-[clamp(10px,2vw,28px)]">
      <header
        ref={shrink}
        className="hero-sticky relative isolate flex flex-col overflow-hidden rounded-bento-lg px-[clamp(18px,2.6vw,34px)] text-[#F2F5EF]"
        style={{ borderRadius: '32px 32px 26px 26px', ['--hero-pb' as any]: '28px', ['--hero-pt' as any]: '20px' }}
      >
        <div className="hero-bg-fade absolute inset-0 rounded-[inherit]" style={{ background: BAND }} />
        <ClientTopbar />
        <div ref={fade} className="fade-collapse relative z-10 flex flex-wrap items-end justify-between gap-4" style={{ ['--collapse' as any]: '120px' }}>
          <div>
            <h1 className="text-[clamp(24px,3.4vw,38px)] font-bold leading-none tracking-[-0.02em]">{title}</h1>
            {sub && <p className="mt-2 text-[13.5px] text-[#F2F5EF]/72">{sub}</p>}
          </div>
          {action}
        </div>
      </header>
      <main className="mt-3.5 rounded-bento-lg bg-panel p-3.5" style={{ viewTransitionName: 'page-body' }}>{children}</main>
    </div>
  )
}
