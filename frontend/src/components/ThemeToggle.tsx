import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'

// Dark is the default; this toggles to the light look and persists the choice.
export function ThemeToggle({ className = '' }: { className?: string }) {
  const [light, setLight] = useState(
    () => typeof document !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'light',
  )
  useEffect(() => {
    const el = document.documentElement
    if (light) el.setAttribute('data-theme', 'light')
    else el.removeAttribute('data-theme')
    try {
      localStorage.setItem('varuna-theme', light ? 'light' : 'dark')
    } catch {}
  }, [light])

  return (
    <button
      onClick={() => setLight((v) => !v)}
      aria-label={light ? 'Switch to dark' : 'Switch to light'}
      className={`grid h-11 w-11 place-items-center rounded-full bg-white/10 text-[#F2F5EF] backdrop-blur-md transition-colors hover:bg-white/[.18] ${className}`}
    >
      {light ? <Sun size={19} /> : <Moon size={19} />}
    </button>
  )
}
