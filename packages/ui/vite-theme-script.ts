import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import type { Plugin } from 'vite'

/**
 * Serves packages/ui/theme.js as /theme.js (dev) and ships it next to
 * index.html (build). index.html loads it in <head>, before the app: an
 * inline script would be blocked by the portals' CSP (script-src 'self').
 */
export function themeScript(): Plugin {
  const source = () => readFileSync(resolve(__dirname, 'theme.js'), 'utf8')
  return {
    name: 'hubra-theme-script',
    configureServer(server) {
      server.middlewares.use('/theme.js', (_req, res) => {
        res.setHeader('Content-Type', 'text/javascript')
        res.end(source())
      })
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'theme.js', source: source() })
    },
  }
}
