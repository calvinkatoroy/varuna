import { ClientTopbar } from './ClientTopbar'
import { ClientDock } from './ClientDock'
import { useScrollThreshold } from '@/lib/useScrollThreshold'

const BAND =
  'radial-gradient(120% 150% at 88% -25%, rgba(34,211,197,.26), transparent 46%),' +
  'linear-gradient(158deg,#0B5FA5 0%,#0A2A43 62%,#060F18 100%)'

// Compact page frame for the client sub-pages (Proposals / Findings / Reports): one merged
// hero (brand/nav/controls + title), matching the cockpit. `position: fixed` (see .hero-sticky
// in index.css) so its own shrink-on-scroll never moves `main` below it - `main` reserves a
// constant gap instead of depending on the hero's live height.
export function ClientShell({
  title, sub, action, children,
}: { title: string; sub?: string; action?: React.ReactNode; children: React.ReactNode }) {
  const shrink = useScrollThreshold<HTMLElement>(60, 'is-shrunk')
  const fade = useScrollThreshold<HTMLDivElement>(55, 'is-faded')
  return (
    <div className="mx-auto max-w-[1380px] p-[clamp(10px,2vw,28px)] pb-[92px] md:pb-[clamp(10px,2vw,28px)]">
      <a href="#main" className="sr-only rounded-pill bg-cta-bg px-4 py-2 text-[13px] font-semibold text-cta-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:px-5 focus:py-3 focus:shadow-lg">Skip to content</a>
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
      {/* Invisible spacer reserving room for the hero at its EXPANDED size - fixed height, never
          toggles a class, never transitions - see ClientCockpit for why. */}
      <div aria-hidden className="hero-spacer pointer-events-none" style={{ height: 178 }} />
      <main id="main" tabIndex={-1} className="mt-3.5 rounded-bento-lg bg-panel p-3.5 focus:outline-none" style={{ viewTransitionName: 'page-body' }}>{children}</main>
      <ClientDock />
    </div>
  )
}
