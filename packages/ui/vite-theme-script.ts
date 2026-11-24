import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import type { Plugin } from 'vite'

/**
 * Serves @bitsandbricks/ui's theme script as /theme.js (dev) and ships it
 * next to index.html (build). index.html loads it in <head>, before the app,
 * with data-cookie="hubra_theme": an inline script would be blocked by the
 * portals' CSP (script-src 'self'). Resolved from the app being built.
 */
export function themeScript(): Plugin {
  const file = createRequire(join(process.cwd(), 'package.json')).resolve(
    '@bitsandbricks/ui/theme-script.js',
  )
  const source = () => readFileSync(file, 'utf8')
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
