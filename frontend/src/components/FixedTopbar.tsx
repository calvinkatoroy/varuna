import { ClientTopbar } from './ClientTopbar'

// The client chrome (brand, nav pill, theme/notifications/account) as its own floating bar,
// always fixed at the top - never resizes, never scrolls, matches the bottom PrototypeSwitcher's
// floating-pill language. Its own dark tint keeps it legible over whatever scrolls underneath
// (the hero band, the light bento panel), since its content is styled for a dark backdrop.
export function FixedTopbar() {
  return (
    <div className="fixed inset-x-0 top-0 z-40 flex justify-center px-[clamp(10px,2vw,28px)] pt-[clamp(8px,1.4vw,16px)]">
      <div className="w-full max-w-[1380px] rounded-[26px] bg-[#0d1f18]/85 px-[clamp(14px,2vw,24px)] py-2.5 shadow-[0_16px_50px_rgba(0,0,0,.35)] backdrop-blur-md">
        <ClientTopbar />
      </div>
    </div>
  )
}
