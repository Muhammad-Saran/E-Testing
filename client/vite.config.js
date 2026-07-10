import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// React dev server runs on 5173; the Django API is on 8000 (see src/api/client.js).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
})
