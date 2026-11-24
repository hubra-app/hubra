import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import '@mantine/core/styles.css'
import '@mantine/dates/styles.css'
import '@mantine/notifications/styles.css'
import '@mantine/tiptap/styles.css'
import '@bitsandbricks/tokens/tokens.css'
import '@bitsandbricks/ui/styles.css'
import '@bitsandbricks/widgets/styles.css'
// After the shared styles and before the app's own, so those win.
import '@hubra/ui/ui.css'
import { BuildBadge } from '@hubra/ui'
import './index.css'
import './locales/i18n'
import App from '@/App.tsx'
import { ROUTER_BASENAME } from '@/clubBase'
import { queryClient } from '@/queryClient'
import { BrandedMantineProvider } from '@/components/BrandedMantineProvider'
import { setupPwa } from '@/pwa'

setupPwa()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrandedMantineProvider>
      <BuildBadge />
      <BrowserRouter basename={ROUTER_BASENAME}>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </BrowserRouter>
    </BrandedMantineProvider>
  </StrictMode>,
)
