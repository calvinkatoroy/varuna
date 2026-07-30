import { ClientTopbar } from './ClientTopbar'
import { useHeroShrink } from '@/lib/useHeroShrink'

const BAND =
  'radial-gradient(120% 150% at 88% -25%, rgba(242,106,67,.28), transparent 46%),' +
  'linear-gradient(158deg,#154739 0%,#0d211b 62%,#070908 100%)'

// Compact page frame for the client sub-pages (Proposals / Findings / Reports): same brand +
// nav + top-right controls as the cockpit hero, on a shorter band, then a panel for content.
// The hero is sticky + shrinks on scroll (useHeroShrink) so the nav pill barely moves, matching
// the cockpit and keeping page transitions stable. The shrink ref lives on the OUTER wrapper (not
// the header) so --over cascades down to <main>'s .content-offset too, see useHeroShrink.
export function ClientShell({
  title, sub, action, children,
}: { title: string; sub?: string; action?: React.ReactNode; children: React.ReactNode }) {
  const hero = useHeroShrink<HTMLElement>(100)
  return (
    <div ref={hero} className="mx-auto max-w-[1380px] p-[clamp(10px,2vw,28px)]">
      <header
        className="hero-sticky relative isolate flex flex-col overflow-hidden rounded-bento-lg px-[clamp(18px,2.6vw,34px)] text-[#F2F5EF]"
        style={{ background: BAND, borderRadius: '32px 32px 26px 26px', ['--hero-pb' as any]: '28px', ['--hero-pt' as any]: '20px' }}
      >
        <ClientTopbar />
        <div className="hero-fade mt-3.5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[clamp(24px,3.4vw,38px)] font-bold leading-none tracking-[-0.02em]">{title}</h1>
            {sub && <p className="mt-2 text-[13.5px] text-[#F2F5EF]/72">{sub}</p>}
          </div>
          {action}
        </div>
      </header>
      <main className="content-offset rounded-bento-lg bg-panel p-3.5" style={{ viewTransitionName: 'page-body' }}>{children}</main>
    </div>
  )
}
