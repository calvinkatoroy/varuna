import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Dev: proxy the public API to the FastAPI browser app on :8000, and the agent API to :8001
// (mirrors Caddy's /api and /agent routing in prod, so VARUNA_URL=<origin> works in both).
// The private-plane API (findings/reports) is cross-origin at VITE_PRIVATE_API (Tailscale
// host in prod); it is called with its full URL and allowed via CORS.
// Mock-first: with VITE_MOCK=1 (default in .env) the app runs standalone with fixtures, so
// `npm run dev` needs no backend at all — the proxy only matters once VITE_MOCK=0.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000', '/agent': 'http://localhost:8001' },
  },
})
