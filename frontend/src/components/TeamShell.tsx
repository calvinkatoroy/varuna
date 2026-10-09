import { NavLink, Outlet } from 'react-router-dom'
import { BrandMark } from './BrandMark'
import { ThemeToggle } from './ThemeToggle'
import { TeamAccount } from './TeamAccount'
import { ShellSlotsProvider, useShellSlots } from './ShellSlots'
import { TEAM_NAV } from '@/lib/navItems'

// The security-team frame, mounted ONCE for the team pages (a layout route): brand, Board/Findings nav, theme
// and account menu are permanent. A page fills the title slot and the action slot (ShellTitle / ShellActions).
// No backdrop-filter in this header: it packs many controls in one row (see ClientTopbar's ctrl comment).
export function TeamShell() {
  const { slots, titleRef, actionsRef } = useShellSlots()
  return (
    <ShellSlotsProvider value={slots}>
      <div className="mx-auto max-w-[1500px] p-[clamp(10px,2vw,28px)]">
        <a href="#main" className="sr-only rounded-pill bg-cta-bg px-4 py-2 text-[13px] font-semibold text-cta-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:px-5 focus:py-3 focus:shadow-lg">Skip to content</a>
        <header
          className="relative flex flex-wrap items-center gap-4 overflow-hidden rounded-bento-lg px-[clamp(18px,2.4vw,30px)] py-5 text-[#F2F5EF]"
          style={{ background: 'radial-gradient(120% 140% at 88% -20%, rgba(34,211,197,.22), transparent 46%), linear-gradient(158deg,#0B5FA5 0%,#0A2A43 55%,#060F18 100%)' }}
        >
          <div className="flex items-center gap-2.5 text-[20px] font-bold tracking-[-0.02em]">
            <BrandMark size={32} />
            Varuna
          </div>
          <div className="hidden h-6 w-px bg-white/15 sm:block" />
          <nav aria-label="Main" className="flex items-center gap-1 rounded-pill bg-white/[.16] p-1">
            {TEAM_NAV.map(({ label, to, end, warm }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onPointerEnter={warm}
                onFocus={warm}
                onPointerDown={warm}
                className={({ isActive }) =>
                  `rounded-pill px-4 py-3 text-[13px] md:px-3.5 md:py-1.5 ${isActive ? 'bg-[#F4F6F1] font-semibold text-[#12140F]' : 'font-medium text-[#F2F5EF]/70'}`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div ref={titleRef} className="min-w-0" />
          <div className="ml-auto flex max-w-full flex-wrap items-center gap-2.5">
            <div ref={actionsRef} className="contents" />
            <ThemeToggle className="hidden h-11 w-11 place-items-center rounded-full bg-white/[.16] text-[#F2F5EF] transition-colors hover:bg-white/25 md:grid" />
            <TeamAccount />
          </div>
        </header>
        <main id="main" tabIndex={-1} className="focus:outline-none"><Outlet /></main>
        <div id="route-announcer" role="status" aria-live="polite" className="sr-only" />
      </div>
    </ShellSlotsProvider>
  )
}
