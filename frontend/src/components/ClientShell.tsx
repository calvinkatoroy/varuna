import { ClientTopbar } from './ClientTopbar'

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
        <ClientTopbar />
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
