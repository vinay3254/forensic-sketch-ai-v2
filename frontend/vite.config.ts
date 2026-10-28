import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // same origin as the SPA, so the SameSite=Strict session cookie is sent
    proxy: { '/api': backend, '/health': backend },
  },
})
