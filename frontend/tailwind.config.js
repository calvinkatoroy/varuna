/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // design.md · theme: Cobalt (dark execution) — values live in src/index.css :root
        paper: 'var(--color-paper)',
        'paper-2': 'var(--color-paper-2)',
        'paper-3': 'var(--color-paper-3)',
        ink: 'var(--color-ink)',
        'ink-muted': 'var(--color-ink-muted)',
        'ink-faint': 'var(--color-ink-faint)',
        rule: 'var(--color-rule)',
        accent: 'var(--color-accent)',
        'accent-ink': 'var(--color-accent-ink)',
        focus: 'var(--color-focus)',
        crit: 'var(--color-crit)',
        high: 'var(--color-high)',
        med: 'var(--color-med)',
        low: 'var(--color-low)',
        info: 'var(--color-info)',
      },
      fontFamily: {
        display: ['var(--font-display)'],
        body: ['var(--font-body)'],
        mono: ['var(--font-mono)'],
      },
      fontSize: {
        display: ['var(--text-display)', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
      },
      spacing: {
        '3xs': '0.25rem',
        '2xs': '0.5rem',
        xs: '0.75rem',
        sm: '1rem',
        md: '1.5rem',
        lg: '2rem',
        xl: '3rem',
        '2xl': '4.5rem',
      },
      borderRadius: {
        input: 'var(--radius-input)',
        card: 'var(--radius-card)',
        pill: 'var(--radius-pill)',
      },
      transitionTimingFunction: {
        out: 'var(--ease-out)',
      },
      transitionDuration: {
        short: '150ms',
        med: '220ms',
      },
    },
  },
  plugins: [],
}
