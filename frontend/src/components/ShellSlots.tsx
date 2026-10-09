import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

// The shell owns the header band; a page only hands it content. Two slots: the title block and the action
// buttons. Both are real elements of the shell, so they exist before any page renders and a tab switch only
// swaps what is inside them.
type Slots = { title: HTMLElement | null; actions: HTMLElement | null }
const Ctx = createContext<Slots>({ title: null, actions: null })
export const ShellSlotsProvider = Ctx.Provider

export function useShellSlots() {
  const [title, setTitle] = useState<HTMLElement | null>(null)
  const [actions, setActions] = useState<HTMLElement | null>(null)
  const slots = useMemo(() => ({ title, actions }), [title, actions])
  return { slots, titleRef: setTitle, actionsRef: setActions }
}

/** The page name in the header. `size="band"` is the compact team band; `kicker` is the small line above. */
export function ShellTitle({ title, sub, kicker, announce, size = 'hero' }: {
  title: string; sub?: ReactNode; kicker?: ReactNode; announce?: string; size?: 'hero' | 'band'
}) {
  const { title: el } = useContext(Ctx)
  const say = announce ?? title
  useEffect(() => {
    document.title = `${say} - Varuna`
    const live = document.getElementById('route-announcer')   // polite live region in the shell
    if (live) live.textContent = say
  }, [say])
  if (!el) return null
  return createPortal(
    <>
      {kicker && <div className="flex items-center gap-2 text-[12.5px] text-[#F2F5EF]/70">{kicker}</div>}
      <h1 className={size === 'hero' ? 'text-[clamp(24px,3.4vw,38px)] font-bold leading-none tracking-[-0.02em]' : 'text-[22px] font-bold tracking-[-0.02em]'}>{title}</h1>
      {sub && <p className="mt-2 text-[13.5px] text-[#F2F5EF]/72">{sub}</p>}
    </>,
    el,
  )
}

/** The page's header buttons (New task, filters). */
export function ShellActions({ children }: { children: ReactNode }) {
  const { actions } = useContext(Ctx)
  return actions ? createPortal(children, actions) : null
}
