import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

// Component tests: npm test
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      css: false,
    },
  }),
)
