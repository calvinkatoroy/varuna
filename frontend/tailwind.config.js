/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // SRS §3.1 dark theme + severity palette
        bg: '#0e1117',
        card: '#161b22',
        border: '#30363d',
        crit: '#ff4b4b',
        high: '#ff6b35',
        med: '#ffa500',
        low: '#4CAF50',
        info: '#2196F3',
      },
    },
  },
  plugins: [],
}
