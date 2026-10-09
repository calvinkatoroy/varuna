import { Outlet } from 'react-router-dom'
import { ClientTopbar } from './ClientTopbar'
import { ClientDock } from './ClientDock'
import { ShellSlotsProvider, useShellSlots } from './ShellSlots'
import { useScrollThreshold } from '@/lib/useScrollThreshold'

const BAND =
  'radial-gradient(120% 150% at 88% -25%, rgba(34,211,197,.26), transparent 46%),' +
  'linear-gradient(158deg,#0B5FA5 0%,#0A2A43 62%,#060F18 100%)'

// The client frame, mounted ONCE for every client tab (a layout route): brand, nav, controls, title block, phone
// dock. A tab switch only swaps the page in the outlet; the pages fill the two slots through ShellTitle /
// ShellActions. `position: fixed` (see .hero-sticky in index.css) so its own shrink-on-scroll never moves `main`:
// `main` sits below a constant spacer. Pass `children` to render a page outside the router outlet (the blurred
// pre-activation view, Profile).
export function ClientShell({ children }: { children?: React.ReactNode }) {
  const shrink = useScrollThreshold<HTMLElement>(60, 'is-shrunk')
  const fade = useScrollThreshold<HTMLDivElement>(55, 'is-faded')
  const { slots, titleRef, actionsRef } = useShellSlots()
  return (
    <ShellSlotsProvider value={slots}>
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
            <div ref={titleRef} className="min-w-0" />
            <div ref={actionsRef} className="flex flex-wrap items-center gap-[11px]" />
          </div>
        </header>
        {/* Invisible spacer reserving room for the hero at its EXPANDED size: fixed height, never toggles. */}
        <div aria-hidden className="hero-spacer pointer-events-none" style={{ height: 178 }} />
        <main id="main" tabIndex={-1} className="mt-3.5 focus:outline-none">{children ?? <Outlet />}</main>
        <ClientDock />
        <div id="route-announcer" role="status" aria-live="polite" className="sr-only" />
      </div>
    </ShellSlotsProvider>
  )
}
