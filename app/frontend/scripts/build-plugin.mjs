// Builds a plugin's frontend into <plugin>/frontend/dist/plugin.js.
//
//   npm run build:plugin                    every plugin in ../../plugins
//   npm run build:plugin -- ../../plugins/keys /path/to/my-plugin
//   npm run build:plugin -- --watch ../../plugins/keys
//
// The bundle is one IIFE.  React, Mantine, react-query, react-router,
// react-i18next and @hubra/plugin-sdk are not bundled: the plugin gets the
// app's own copies from window.HubraPluginHost (src/plugins/host.ts), so it
// shares the app's contexts.  Anything else it imports (icons, say) is
// bundled.  Bare imports resolve against this app's node_modules, so a
// plugin folder needs no node_modules of its own.
//
// The host hands over only the names host.ts lists, so the build fails when
// a plugin imports any other name from those libraries.  The bundle carries
// the host API version it was built for and does nothing in an app with
// another one.
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'vite'
import react from '@vitejs/plugin-react'

const app = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const host = 'window.HubraPluginHost'
const hostSource = readFileSync(join(app, 'src', 'plugins', 'host.ts'), 'utf8')

const HOST_API = Number(hostSource.match(/export const HOST_API = (\d+)/)?.[1])
if (!HOST_API) throw new Error('src/plugins/host.ts: no HOST_API')

const GLOBALS = {
  react: `${host}.libs.react`,
  'react-dom': `${host}.libs.reactDom`,
  'react/jsx-runtime': `${host}.libs.jsxRuntime`,
  'react-router-dom': `${host}.libs.routerDom`,
  '@mantine/core': `${host}.libs.mantineCore`,
  '@mantine/hooks': `${host}.libs.mantineHooks`,
  '@mantine/notifications': `${host}.libs.mantineNotifications`,
  '@tanstack/react-query': `${host}.libs.reactQuery`,
  'react-i18next': `${host}.libs.reactI18next`,
  '@hubra/plugin-sdk': `${host}.sdk`,
}

/** The names host.ts hands over, by library; libraries it hands over whole are absent. */
function hostNames() {
  const names = {}
  for (const m of hostSource.matchAll(/^import \{([^}]*)\} from '([^']+)'/gm)) {
    names[m[2]] = new Set(
      m[1]
        .split(',')
        .map((n) => n.trim().split(/\s+as\s+/)[0])
        .filter(Boolean),
    )
  }
  return names
}

/** Fail the build when the plugin imports a name the host does not hand over. */
function checkHostImports() {
  const allowed = hostNames()
  return {
    name: 'hubra-check-host-imports',
    transform(code, id) {
      if (id.includes('node_modules') || !/\.[jt]sx?$/.test(id)) return null
      const errors = []
      for (const m of code.matchAll(/import\s+(type\s+)?([^'";]*?)\s+from\s+['"]([^'"]+)['"]/g)) {
        const [, isType, clause, lib] = m
        const names = allowed[lib]
        if (isType || !names) continue
        const named = clause.match(/\{([^}]*)\}/)
        if (!named || /^[\w$]+\s*,|\*/.test(clause.replace(/\{[^}]*\}/, ''))) {
          errors.push(`import only named exports from '${lib}' (import { … } from '${lib}')`)
          continue
        }
        for (const raw of named[1].split(',')) {
          const n = raw.trim()
          if (!n || n.startsWith('type ')) continue
          const name = n.split(/\s+as\s+/)[0]
          if (!names.has(name)) errors.push(`'${name}' from '${lib}' is not available to plugins`)
        }
      }
      if (errors.length)
        this.error(`${id}:\n  ${errors.join('\n  ')}\n  (the names plugins can use are in app/frontend/src/plugins/host.ts)`)
      return null
    },
  }
}

/** Resolve bare imports from the plugin as if this app had made them. */
function resolveFromApp() {
  const anchor = join(app, 'src', 'main.tsx')
  return {
    name: 'hubra-resolve-from-app',
    enforce: 'pre',
    async resolveId(source, importer, options) {
      if (!importer || source in GLOBALS || /^[./]|^\0|^[a-zA-Z]:/.test(source)) return null
      if (importer.startsWith(app)) return null
      return this.resolve(source, anchor, { ...options, skipSelf: true })
    },
  }
}

function pluginId(dir) {
  const m = readFileSync(join(dir, 'plugin.yaml'), 'utf8').match(/^id:\s*["']?([\w-]+)/m)
  if (!m) throw new Error(`${dir}: plugin.yaml has no id`)
  return m[1]
}

async function buildOne(dir, watch) {
  const entry = ['index.tsx', 'index.ts']
    .map((f) => join(dir, 'frontend', 'src', f))
    .find(existsSync)
  if (!entry) return false
  const id = pluginId(dir)
  await build({
    configFile: false,
    root: join(dir, 'frontend'),
    logLevel: 'warn',
    plugins: [checkHostImports(), resolveFromApp(), react()],
    define: { 'process.env.NODE_ENV': '"production"' },
    build: {
      outDir: join(dir, 'frontend', 'dist'),
      emptyOutDir: true,
      sourcemap: false,
      minify: true,
      watch: watch ? {} : null,
      lib: {
        entry,
        formats: ['iife'],
        name: `HubraPlugin_${id.replace(/\W/g, '_')}`,
        fileName: () => 'plugin.js',
      },
      rollupOptions: {
        external: Object.keys(GLOBALS),
        output: {
          globals: GLOBALS,
          // Run only in an app with the host API this was built for.
          banner:
            `/* Hubra plugin: ${id}, host API ${HOST_API} */\n` +
            `(function () {\n` +
            `if ((${host} && ${host}.api) !== ${HOST_API}) {\n` +
            `  console.error('[plugin ${id}] built for host API ${HOST_API}, this app has ' + (${host} && ${host}.api));\n` +
            `  return;\n` +
            `}`,
          footer: '})();',
        },
      },
    },
  })
  console.log(`${id}: ${join(dir, 'frontend', 'dist', 'plugin.js')}`)
  return true
}

const args = process.argv.slice(2)
const watch = args.includes('--watch')
let dirs = args.filter((a) => a !== '--watch').map((d) => resolve(d))
if (dirs.length === 0) {
  const root = resolve(app, '..', '..', 'plugins')
  dirs = readdirSync(root, { withFileTypes: true })
    .filter((d) => d.isDirectory() && existsSync(join(root, d.name, 'plugin.yaml')))
    .map((d) => join(root, d.name))
}
for (const dir of dirs) {
  if (!(await buildOne(dir, watch))) console.log(`${dir}: no frontend/src/index.tsx, skipped`)
}
