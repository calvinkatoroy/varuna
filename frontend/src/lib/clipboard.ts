import { toast } from './toast'

// The Clipboard API only exists in secure contexts (https or localhost). The team plane is plain http on the
// Tailscale address, so fall back to a hidden textarea and execCommand('copy').
function legacyCopy(text: string): boolean {
  const prev = document.activeElement as HTMLElement | null
  const ta = document.createElement('textarea')
  ta.value = text
  ta.setAttribute('readonly', '')
  ta.setAttribute('aria-hidden', 'true')
  ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none'
  document.body.appendChild(ta)
  try {
    ta.select()
    return document.execCommand('copy')
  } catch { return false } finally {
    document.body.removeChild(ta)
    prev?.focus?.()
  }
}

/** Select the text of `node` so Ctrl+C works when copying was not possible. */
export function selectText(node: HTMLElement | null): void {
  if (!node) return
  const r = document.createRange()
  r.selectNodeContents(node)
  const s = window.getSelection()
  s?.removeAllRanges()
  s?.addRange(r)
}

/** Copy `text`; says so with a toast either way. Returns whether it worked (on false the caller should show the
 *  text and call `selectText`). */
export async function copyText(text: string): Promise<boolean> {
  let ok = false
  try {
    if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); ok = true }
  } catch { /* fall through to the legacy path */ }
  if (!ok) ok = legacyCopy(text)
  toast(ok ? 'Copied' : 'Could not copy. The text is selected: press Ctrl+C to copy it.')
  return ok
}
