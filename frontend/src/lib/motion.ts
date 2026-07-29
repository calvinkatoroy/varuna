import anime from 'animejs'

const reduced = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

// Staggered fade/rise for a grid of tiles on mount.
export function revealTiles(selector: string) {
  if (reduced()) {
    document.querySelectorAll(selector).forEach((e) => ((e as HTMLElement).style.opacity = '1'))
    return
  }
  anime({
    targets: selector,
    translateY: [14, 0],
    opacity: [0, 1],
    delay: anime.stagger(55),
    duration: 520,
    easing: 'easeOutCubic',
  })
}

// Count-up a number into an element's text.
export function tickNumber(el: HTMLElement | null, to: number, suffix = '') {
  if (!el) return
  if (reduced()) {
    el.textContent = String(to) + suffix
    return
  }
  const obj = { v: 0 }
  anime({
    targets: obj,
    v: to,
    round: 1,
    duration: 850,
    easing: 'easeOutCubic',
    update: () => {
      el.textContent = String(obj.v) + suffix
    },
  })
}

// Quick press feedback on a button.
export function press(el: HTMLElement) {
  if (reduced()) return
  anime({ targets: el, scale: [1, 0.9, 1], duration: 260, easing: 'easeOutQuad' })
}

// Clean rise: elements lift into place with a long expo ease. Calm, not bouncy — the
// restrained entrance a minimalist-bold page wants (no rotation, no stagger gimmicks).
export function rise(selector: string, stagger = 70) {
  if (reduced()) {
    document.querySelectorAll(selector).forEach((e) => ((e as HTMLElement).style.opacity = '1'))
    return
  }
  anime({
    targets: selector,
    translateY: [28, 0],
    opacity: [0, 1],
    delay: anime.stagger(stagger),
    duration: 900,
    easing: 'easeOutExpo',
  })
}

// Magnetic hover: the element eases toward the cursor while hovered, then glides back to
// rest. The felt microinteraction on buttons/arrows. Returns a cleanup fn. No overshoot.
export function magnetic(el: HTMLElement | null, strength = 0.4): () => void {
  if (!el || reduced()) return () => {}
  const move = (e: MouseEvent) => {
    const r = el.getBoundingClientRect()
    anime.set(el, { translateX: (e.clientX - (r.left + r.width / 2)) * strength, translateY: (e.clientY - (r.top + r.height / 2)) * strength })
  }
  const leave = () => anime({ targets: el, translateX: 0, translateY: 0, duration: 650, easing: 'easeOutQuart' })
  el.addEventListener('mousemove', move)
  el.addEventListener('mouseleave', leave)
  return () => { el.removeEventListener('mousemove', move); el.removeEventListener('mouseleave', leave) }
}
