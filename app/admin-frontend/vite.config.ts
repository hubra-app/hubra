import { defineConfig, searchForWorkspaceRoot } from 'vite'
import react from '@vitejs/plugin-react'
import { themeScript } from '../../packages/ui/vite-theme-script'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react(), themeScript()],
  resolve: {
    // packages/ui imports these; take them from this app's node_modules.
    dedupe: ['react', 'react-dom', '@mantine/core', '@tabler/icons-react'],
    alias: {
      '@': resolve(__dirname, 'src'),
      '@hubra/api-client': resolve(__dirname, '../../packages/api-client/src'),
      '@hubra/ui': resolve(__dirname, '../../packages/ui/src'),
    },
  },
  server: {
    // packages/ui (shared CSS and fonts) lives outside the app root.
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), resolve(__dirname, '../../packages')] },
    host: '0.0.0.0',
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    modulePreload: false,
    sourcemap: false,
    // No manualChunks: forcing all of Mantine into one chunk made every page
    // load it whole. Screens load per tab (nav.tsx), shared code splits itself.
  },
})
