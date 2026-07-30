import { FixedTopbar } from './FixedTopbar'
import { useScrollFade } from '@/lib/useScrollFade'

const BAND =
  'radial-gradient(120% 150% at 88% -25%, rgba(242,106,67,.28), transparent 46%),' +
  'linear-gradient(158deg,#154739 0%,#0d211b 62%,#070908 100%)'

// Compact page frame for the client sub-pages (Proposals / Findings / Reports): the same
// floating fixed topbar as the cockpit (FixedTopbar, always the same size, never scrolls), then
// a plain normal-flow title band that scrolls away like any other content, then a panel.
export function ClientShell({
  title, sub, action, children,
}: { title: string; sub?: string; action?: React.ReactNode; children: React.ReactNode }) {
  const fade = useScrollFade<HTMLElement>(70)
  return (
    <div className="mx-auto max-w-[1380px] p-[clamp(10px,2vw,28px)]">
      <FixedTopbar />
      <div className="h-[76px]" />
      <header
        ref={fade}
        className="relative isolate flex flex-col overflow-hidden rounded-bento-lg px-[clamp(18px,2.6vw,34px)] py-[clamp(18px,2.2vw,26px)] text-[#F2F5EF]"
        style={{ background: BAND, borderRadius: '32px 32px 26px 26px' }}
      >
        <div className="flex flex-wrap items-end justify-between gap-4">
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
