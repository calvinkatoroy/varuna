import { Outlet } from 'react-router-dom'
import { BrandMark } from './BrandMark'
import { TeamAccount } from './TeamAccount'

// The system administrator's frame: the console is its whole app (no tenant data), so the header has no nav.
export function AdminShell() {
  return (
    <div className="mx-auto max-w-[1100px] p-[clamp(10px,2vw,28px)]">
      <a href="#main" className="sr-only rounded-pill bg-cta-bg px-4 py-2 text-[13px] font-semibold text-cta-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:px-5 focus:py-3 focus:shadow-lg">Skip to content</a>
      <header className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-bento-lg bg-card px-5 py-3.5 sm:px-6">
        <span className="flex items-center gap-2.5 text-[18px] font-bold tracking-[-0.02em] text-ink"><BrandMark size={28} /> <span className="hidden sm:inline">Varuna</span></span>
        <h1 className="text-[18px] font-bold text-ink">Administration</h1>
        <div className="ml-auto"><TeamAccount /></div>
      </header>
      <main id="main" tabIndex={-1} className="focus:outline-none"><Outlet /></main>
    </div>
  )
}
