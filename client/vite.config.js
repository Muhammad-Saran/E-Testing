import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// React dev server runs on 5173; the Django API is on 8000 (see src/api/client.js).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      output: {
        // Charts are only needed on dashboards/analytics; keep them in their own cached chunk.
        manualChunks: { charts: ['chart.js', 'react-chartjs-2'] },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    include: ['src/**/*.test.{js,jsx}'],
    css: false,
  },
})
