import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    // packages/ui imports these; take them from this app's node_modules.
    dedupe: ['react', 'react-dom', '@mantine/core'],
    alias: {
      '@': resolve(__dirname, 'src'),
      '@hubra/api-client': resolve(__dirname, '../../packages/api-client/src'),
      '@hubra/ui': resolve(__dirname, '../../packages/ui/src'),
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
  // No manualChunks: forcing a library into one chunk makes every page load
  // all of it (the rich text editor came along with Mantine that way).  The
  // default splitting keeps what only some screens use in their chunks.
  build: {
    modulePreload: false,
    sourcemap: false,
  },
})
