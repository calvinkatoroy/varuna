import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'

const DEFAULT_CLASS = 'grid h-11 w-11 place-items-center rounded-full bg-white/10 text-[#F2F5EF] backdrop-blur-md transition-colors hover:bg-white/[.18]'

// Dark is the default; this toggles to the light look and persists the choice. `className`, if
// given, REPLACES the default look entirely (not appended) - mixing both would leave conflicting
// utility classes (e.g. two different `bg-*`) whose winner depends on Tailwind's generated CSS
// order, not on where they appear in the class string.
export function ThemeToggle({ className = DEFAULT_CLASS }: { className?: string }) {
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
      className={className}
    >
      {light ? <Sun size={19} /> : <Moon size={19} />}
    </button>
  )
}
