import anime from 'animejs'

const reduced = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

// Quick press feedback on a button (a micro-interaction; there are no entrance or route animations).
export function press(el: HTMLElement) {
  if (reduced()) return
  anime({ targets: el, scale: [1, 0.9, 1], duration: 260, easing: 'easeOutQuad' })
}
