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
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'vite'
import react from '@vitejs/plugin-react'

const app = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const host = 'window.HubraPluginHost'

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
    plugins: [resolveFromApp(), react()],
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
        output: { globals: GLOBALS, banner: `/* Hubra plugin: ${id} */` },
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
