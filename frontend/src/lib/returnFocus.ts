import { useCallback, useRef } from 'react'

/** A drawer opened from code (no Radix trigger) loses focus to <body> when it closes. `remember()` in the
 *  open handler keeps the control that was focused; pass `onCloseAutoFocus` to `DrawerContent` to give it back. */
export function useReturnFocus() {
  const opener = useRef<HTMLElement | null>(null)
  const remember = useCallback(() => { opener.current = document.activeElement as HTMLElement | null }, [])
  const onCloseAutoFocus = useCallback((e: Event) => {
    const el = opener.current
    opener.current = null
    if (el?.isConnected) { e.preventDefault(); el.focus() }
  }, [])
  return { remember, onCloseAutoFocus }
}
