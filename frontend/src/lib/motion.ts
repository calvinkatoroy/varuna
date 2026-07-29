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

// Dossier reveal: case-file entries settle in like sheets laid onto a desk — a soft rise
// plus a hair of rotation, slower and calmer than the generic fade-up.
export function inkSettle(selector: string) {
  if (reduced()) {
    document.querySelectorAll(selector).forEach((e) => ((e as HTMLElement).style.opacity = '1'))
    return
  }
  anime({
    targets: selector,
    translateY: [12, 0],
    rotate: [-0.5, 0],
    opacity: [0, 1],
    delay: anime.stagger(75),
    duration: 620,
    easing: 'easeOutCubic',
  })
}

// Stamp press: a rubber stamp coming down onto the page. Rotation lives on the wrapper, so
// this only drives scale + opacity and won't fight the tilt. No bounce (UI-state easing).
export function stampIn(el: HTMLElement | null, delay = 260) {
  if (!el) return
  if (reduced()) { el.style.opacity = '1'; return }
  anime({ targets: el, scale: [1.3, 1], opacity: [0, 1], duration: 380, delay, easing: 'easeOutCubic' })
}
