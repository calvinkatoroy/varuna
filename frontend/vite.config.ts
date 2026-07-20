import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: proxy the public API to the FastAPI browser app on :8000, and the agent API to :8001
// (mirrors Caddy's /api and /agent routing in prod, so VARUNA_URL=<origin> works in both).
// The private-plane API (findings/reports) is cross-origin at VITE_PRIVATE_API (Tailscale
// host in prod); it is called with its full URL and allowed via CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000', '/agent': 'http://localhost:8001' },
  },
})
