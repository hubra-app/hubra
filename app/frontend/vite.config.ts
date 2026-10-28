import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@hubra/api-client': resolve(__dirname, '../../packages/api-client/src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // Local dev: proxy /api/* to Flask backend (mirrors Caddy routing in Docker)
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    modulePreload: false,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react-router-dom')) return 'react-vendor'
            if (id.includes('/react/') || id.includes('/react-dom/')) return 'react-vendor'
            if (id.includes('@mantine')) return 'mantine'
            if (id.includes('@tabler/icons-react')) return 'icons'
            if (id.includes('@tanstack/react-query')) return 'query'
            if (id.includes('i18next') || id.includes('react-i18next')) return 'i18n'
          }
        },
      },
    },
  },
})
