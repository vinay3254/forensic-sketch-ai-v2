import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// BACKEND_URL lets a second dev stack run beside the usual one
const backend = process.env.BACKEND_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // same origin as the SPA, so the SameSite=Strict session cookie is sent
    proxy: { '/api': backend, '/health': backend },
  },
})
