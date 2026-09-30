// Flip the light/dark look from anywhere (the header toggle keeps its own state; this is for the
// phone account menu where the toggle button itself is folded away).
export function toggleTheme(): void {
  const el = document.documentElement
  const light = el.getAttribute('data-theme') !== 'light'
  if (light) el.setAttribute('data-theme', 'light')
  else el.removeAttribute('data-theme')
  try { localStorage.setItem('varuna-theme', light ? 'light' : 'dark') } catch {}
}
