import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy /v1 to the local FastAPI so the dev server and API share an origin.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/v1': 'http://127.0.0.1:8000' } },
})
